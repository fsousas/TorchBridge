/* Linux transport for TorchBridge. One connection per owner thread.
 * Qt rasterizes the SAME overlay as Windows; this module only presents pixels
 * and sends Wayland input. Protocols retain their upstream licenses in protocols/.
 */
#define _GNU_SOURCE
#include <wayland-client.h>
#include <xkbcommon/xkbcommon.h>
#include <sys/mman.h>
#include <unistd.h>
#include <poll.h>
#include <time.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include "wlr-layer-shell-unstable-v1.h"
#include "wlr-virtual-pointer-unstable-v1.h"
#include "virtual-keyboard-unstable-v1.h"

#define MAX_OUTPUTS 32
#define EVENT_COUNT 64
struct output { struct wl_output *object; char name[128]; uint32_t global; };
struct buffer { struct wl_buffer *object; void *pixels; size_t size; int busy, width, height; };
struct event { int kind, x, y; };
struct bridge {
    struct wl_display *display;
    struct wl_registry *registry;
    struct wl_compositor *compositor;
    struct wl_shm *shm;
    struct wl_seat *seat;
    struct wl_pointer *pointer;
    struct zwlr_layer_shell_v1 *shell;
    struct zwlr_virtual_pointer_manager_v1 *pointer_manager;
    struct zwp_virtual_keyboard_manager_v1 *keyboard_manager;
    struct zwlr_virtual_pointer_v1 *virtual_pointer;
    struct zwp_virtual_keyboard_v1 *keyboard;
    struct xkb_context *xkb;
    struct xkb_keymap *keymap;
    struct xkb_state *state;
    struct output outputs[MAX_OUTPUTS];
    int output_count, configured, closed, monitor;
    struct wl_surface *surface;
    struct zwlr_layer_surface_v1 *layer;
    struct buffer buffers[3];
    struct wl_surface *cursor_surface;
    struct buffer cursor_buffer;
    int px, py, read_event, write_event;
    struct event events[EVENT_COUNT];
    unsigned char held[768];
    unsigned int buttons;
};
static _Thread_local char last_error[256];
const char *tb_error(void) { return last_error; }
static uint32_t timestamp(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint32_t)((uint64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000);
}
static int flush(struct bridge *b) {
    if (wl_display_get_error(b->display)) return 0;
    return wl_display_flush(b->display) >= 0 || errno == EAGAIN;
}
int tb_dispatch(struct bridge *b) {
    if (!b || wl_display_get_error(b->display)) return 0;
    while (wl_display_prepare_read(b->display) != 0)
        if (wl_display_dispatch_pending(b->display) < 0) return 0;
    wl_display_flush(b->display);
    struct pollfd p = {wl_display_get_fd(b->display), POLLIN, 0};
    if (poll(&p, 1, 0) > 0) {
        if (wl_display_read_events(b->display) < 0) return 0;
    } else wl_display_cancel_read(b->display);
    return wl_display_dispatch_pending(b->display) >= 0;
}
static void output_geometry(void *d, struct wl_output *o, int32_t x, int32_t y,
        int32_t pw, int32_t ph, int32_t sub, const char *make, const char *model, int32_t tr) {
    (void)d;(void)o;(void)x;(void)y;(void)pw;(void)ph;(void)sub;(void)make;(void)model;(void)tr;
}
static void output_mode(void *d, struct wl_output *o, uint32_t f, int32_t w, int32_t h, int32_t r) {
    (void)d;(void)o;(void)f;(void)w;(void)h;(void)r;
}
static void output_done(void *d, struct wl_output *o) {(void)d;(void)o;}
static void output_scale(void *d, struct wl_output *o, int32_t s) {(void)d;(void)o;(void)s;}
static void output_name(void *d, struct wl_output *o, const char *name) {
    (void)o; snprintf(((struct output *)d)->name, 128, "%s", name);
}
static void output_description(void *d, struct wl_output *o, const char *s) {(void)d;(void)o;(void)s;}
static const struct wl_output_listener output_listener = {
    .geometry=output_geometry, .mode=output_mode, .done=output_done, .scale=output_scale,
    .name=output_name, .description=output_description
};
static void global(void *data, struct wl_registry *r, uint32_t name, const char *iface, uint32_t version) {
    struct bridge *b = data;
#define BIND(I, FIELD, V) if (!strcmp(iface, #I)) b->FIELD = wl_registry_bind(r, name, &I##_interface, version < V ? version : V)
    BIND(wl_compositor, compositor, 4);
    else BIND(wl_shm, shm, 1);
    else if (!strcmp(iface,"wl_seat") && version>=5) b->seat=wl_registry_bind(r,name,&wl_seat_interface,5);
    else BIND(zwlr_layer_shell_v1, shell, 1);
    else BIND(zwlr_virtual_pointer_manager_v1, pointer_manager, 1);
    else BIND(zwp_virtual_keyboard_manager_v1, keyboard_manager, 1);
    else if (!strcmp(iface, "wl_output") && version >= 4 && b->output_count < MAX_OUTPUTS) {
        struct output *o = &b->outputs[b->output_count++];
        o->global = name;
        o->object = wl_registry_bind(r, name, &wl_output_interface, 4);
        wl_output_add_listener(o->object, &output_listener, o);
    }
#undef BIND
}
static void removed(void *data, struct wl_registry *r, uint32_t name) {
    (void)r; struct bridge *b = data;
    for (int i=0; i<b->output_count; i++) if (b->outputs[i].global == name) {
        b->outputs[i].name[0] = 0;
        if (b->layer && b->monitor == i) b->closed = 1;
    }
}
static const struct wl_registry_listener registry_listener = {global, removed};
static void queue(struct bridge *b, int kind) {
    int next = (b->write_event+1) % EVENT_COUNT;
    if (next == b->read_event) b->read_event = (b->read_event+1) % EVENT_COUNT;
    b->events[b->write_event] = (struct event){kind, b->px, b->py};
    b->write_event = next;
}
static void pointer_enter(void *d, struct wl_pointer *p, uint32_t s, struct wl_surface *sf, wl_fixed_t x, wl_fixed_t y) {
    (void)p;(void)s;(void)sf; struct bridge *b=d;
    b->px=wl_fixed_to_int(x); b->py=wl_fixed_to_int(y); queue(b,1);
    if (b->cursor_surface) {
        wl_pointer_set_cursor(p,s,b->cursor_surface,0,0);
        flush(b);
    }
}
static void pointer_leave(void *d, struct wl_pointer *p, uint32_t s, struct wl_surface *sf) {(void)d;(void)p;(void)s;(void)sf;}
static void pointer_motion(void *d, struct wl_pointer *p, uint32_t t, wl_fixed_t x, wl_fixed_t y) {
    (void)p;(void)t; struct bridge *b=d; b->px=wl_fixed_to_int(x); b->py=wl_fixed_to_int(y); queue(b,1);
}
static void pointer_button(void *d, struct wl_pointer *p, uint32_t s, uint32_t t, uint32_t button, uint32_t state) {
    (void)p;(void)s;(void)t; if (button==0x110 && state==WL_POINTER_BUTTON_STATE_PRESSED) queue(d,2);
}
static void pointer_axis(void *d, struct wl_pointer *p, uint32_t t, uint32_t a, wl_fixed_t v) {(void)d;(void)p;(void)t;(void)a;(void)v;}
static void pointer_frame(void *d, struct wl_pointer *p) {(void)d;(void)p;}
static void pointer_source(void *d, struct wl_pointer *p, uint32_t s) {(void)d;(void)p;(void)s;}
static void pointer_stop(void *d, struct wl_pointer *p, uint32_t t, uint32_t a) {(void)d;(void)p;(void)t;(void)a;}
static void pointer_discrete(void *d, struct wl_pointer *p, uint32_t a, int32_t v) {(void)d;(void)p;(void)a;(void)v;}
static const struct wl_pointer_listener pointer_listener = {
    .enter=pointer_enter, .leave=pointer_leave, .motion=pointer_motion, .button=pointer_button,
    .axis=pointer_axis, .frame=pointer_frame, .axis_source=pointer_source,
    .axis_stop=pointer_stop, .axis_discrete=pointer_discrete
};
static int send_keymap(struct bridge *b, struct xkb_keymap *map) {
    char *text = xkb_keymap_get_as_string(map, XKB_KEYMAP_FORMAT_TEXT_V1);
    if (!text) return 0;
    size_t size = strlen(text)+1;
    int fd = memfd_create("torchbridge-keymap", MFD_CLOEXEC);
    if (fd<0) {free(text); return 0;}
    int ok = ftruncate(fd, size)==0 && write(fd,text,size)==(ssize_t)size;
    if (ok) zwp_virtual_keyboard_v1_keymap(b->keyboard, WL_KEYBOARD_KEYMAP_FORMAT_XKB_V1, fd, size);
    close(fd); free(text); return ok;
}
void tb_close(struct bridge *b);
void *tb_open(int input) {
    struct bridge *b = calloc(1,sizeof(*b));
    if (!b) return NULL;
    last_error[0]=0;
    b->monitor=-1; b->display=wl_display_connect(NULL);
    if (!b->display) {snprintf(last_error,256,"Não foi possível conectar ao Wayland"); free(b); return NULL;}
    b->registry=wl_display_get_registry(b->display);
    wl_registry_add_listener(b->registry,&registry_listener,b);
    if (wl_display_roundtrip(b->display)<0 || wl_display_roundtrip(b->display)<0) goto fail;
    if (input) {
        if (!b->seat || !b->pointer_manager || !b->keyboard_manager) {
            snprintf(last_error,256,"Compositor sem virtual-pointer/virtual-keyboard"); goto fail;
        }
        b->virtual_pointer=zwlr_virtual_pointer_manager_v1_create_virtual_pointer(b->pointer_manager,b->seat);
        b->keyboard=zwp_virtual_keyboard_manager_v1_create_virtual_keyboard(b->keyboard_manager,b->seat);
        b->xkb=xkb_context_new(XKB_CONTEXT_NO_FLAGS);
        struct xkb_rule_names names = {.layout="us"};
        if (!b->xkb) goto fail;
        b->keymap=xkb_keymap_new_from_names(b->xkb,&names,XKB_KEYMAP_COMPILE_NO_FLAGS);
        if (!b->keymap || !(b->state=xkb_state_new(b->keymap)) || !send_keymap(b,b->keymap)) goto fail;
    } else {
        if (!b->shell || !b->shm || !b->compositor || !b->output_count || !b->seat) {
            snprintf(last_error,256,"Compositor sem layer-shell, shm, seat ou wl_output v4"); goto fail;
        }
        b->pointer=wl_seat_get_pointer(b->seat);
        wl_pointer_add_listener(b->pointer,&pointer_listener,b);
    }
    if (wl_display_roundtrip(b->display)<0) goto fail;
    return b;
fail:
    if (!last_error[0]) snprintf(last_error,256,"Falha ao inicializar transporte Wayland");
    tb_close(b); return NULL;
}
int tb_key(struct bridge *b, uint32_t code, int down) {
    if (!b || !b->keyboard || code>=768 || !tb_dispatch(b)) return 0;
    zwp_virtual_keyboard_v1_key(b->keyboard,timestamp(),code,down ? 1 : 0);
    xkb_state_update_key(b->state,code+8,down ? XKB_KEY_DOWN : XKB_KEY_UP);
    zwp_virtual_keyboard_v1_modifiers(b->keyboard,
        xkb_state_serialize_mods(b->state,XKB_STATE_MODS_DEPRESSED),0,0,0);
    b->held[code]=!!down;
    return wl_display_roundtrip(b->display)>=0;
}
int tb_move(struct bridge *b, uint32_t x, uint32_t y, uint32_t w, uint32_t h) {
    if (!b || !b->virtual_pointer || !w || !h || !tb_dispatch(b)) return 0;
    zwlr_virtual_pointer_v1_motion_absolute(b->virtual_pointer,timestamp(),x,y,w,h);
    zwlr_virtual_pointer_v1_frame(b->virtual_pointer);
    return flush(b);
}
int tb_button(struct bridge *b, uint32_t button, int down) {
    if (!b || !b->virtual_pointer || (button!=0x110 && button!=0x111) || !tb_dispatch(b)) return 0;
    zwlr_virtual_pointer_v1_button(b->virtual_pointer,timestamp(),button,down ? 1 : 0);
    zwlr_virtual_pointer_v1_frame(b->virtual_pointer);
    if (down) b->buttons |= 1u<<(button-0x110); else b->buttons &= ~(1u<<(button-0x110));
    return wl_display_roundtrip(b->display)>=0;
}
static void buffer_release(void *d, struct wl_buffer *o) {(void)o; ((struct buffer *)d)->busy=0;}
static const struct wl_buffer_listener buffer_listener={buffer_release};
static void buffer_destroy(struct buffer *b) {
    if (b->object) wl_buffer_destroy(b->object);
    if (b->pixels) munmap(b->pixels,b->size);
    memset(b,0,sizeof(*b));
}
static int buffer_create(struct bridge *b, struct buffer *slot, int w, int h) {
    size_t size=(size_t)w*h*4;
    int fd=memfd_create("torchbridge-overlay",MFD_CLOEXEC);
    if (fd<0) return 0;
    if (ftruncate(fd,size)<0) {close(fd);return 0;}
    void *pixels=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    if (pixels==MAP_FAILED) {close(fd);return 0;}
    struct wl_shm_pool *pool=wl_shm_create_pool(b->shm,fd,(int)size);
    slot->object=wl_shm_pool_create_buffer(pool,0,w,h,w*4,WL_SHM_FORMAT_ARGB8888);
    wl_shm_pool_destroy(pool); close(fd);
    slot->pixels=pixels;slot->size=size;slot->width=w;slot->height=h;
    wl_buffer_add_listener(slot->object,&buffer_listener,slot); return 1;
}
int tb_cursor(struct bridge *b, const void *pixels, int w, int h) {
    if (!b || !b->compositor || !pixels || w<=0 || h<=0 || w>512 || h>512 || b->cursor_surface) return 0;
    if (!buffer_create(b,&b->cursor_buffer,w,h)) return 0;
    memcpy(b->cursor_buffer.pixels,pixels,b->cursor_buffer.size);
    b->cursor_surface=wl_compositor_create_surface(b->compositor);
    wl_surface_attach(b->cursor_surface,b->cursor_buffer.object,0,0);
    wl_surface_damage_buffer(b->cursor_surface,0,0,w,h);
    wl_surface_commit(b->cursor_surface);
    return flush(b);
}
static void layer_configure(void *d, struct zwlr_layer_surface_v1 *s, uint32_t serial, uint32_t w, uint32_t h) {
    (void)w;(void)h; struct bridge *b=d;
    zwlr_layer_surface_v1_ack_configure(s,serial);b->configured=1;
}
static void layer_closed(void *d, struct zwlr_layer_surface_v1 *s) {(void)s;((struct bridge *)d)->closed=1;}
static const struct zwlr_layer_surface_v1_listener layer_listener={layer_configure,layer_closed};
void tb_hide(struct bridge *b) {
    if (!b) return;
    if (b->layer) zwlr_layer_surface_v1_destroy(b->layer);
    if (b->surface) wl_surface_destroy(b->surface);
    b->layer=NULL;b->surface=NULL;b->configured=0;b->closed=0;b->monitor=-1;
    b->read_event=b->write_event=0;
    flush(b);
}
int tb_geometry(struct bridge *b, const char *monitor, int x, int y, int w, int h,
                int kx, int ky, int kw, int kh) {
    if (!b || w<=0 || h<=0 || !tb_dispatch(b)) return 0;
    int index=-1;
    for (int i=0;i<b->output_count;i++) if (!strcmp(b->outputs[i].name,monitor)) index=i;
    if (index<0) return 0;
    if (b->closed || b->monitor!=index) tb_hide(b);
    if (!b->layer) {
        b->surface=wl_compositor_create_surface(b->compositor);
        b->layer=zwlr_layer_shell_v1_get_layer_surface(b->shell,b->surface,b->outputs[index].object,
                                                     ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY,"torchbridge-overlay");
        b->monitor=index;
        zwlr_layer_surface_v1_add_listener(b->layer,&layer_listener,b);
        zwlr_layer_surface_v1_set_anchor(b->layer,ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP|ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT);
        zwlr_layer_surface_v1_set_exclusive_zone(b->layer,-1);
        zwlr_layer_surface_v1_set_keyboard_interactivity(b->layer,0);
    }
    zwlr_layer_surface_v1_set_size(b->layer,w,h);
    zwlr_layer_surface_v1_set_margin(b->layer,y,0,0,x);
    struct wl_region *region=wl_compositor_create_region(b->compositor);
    if (kw>0 && kh>0) wl_region_add(region,kx,ky,kw,kh);
    wl_surface_set_input_region(b->surface,region);wl_region_destroy(region);
    wl_surface_commit(b->surface);
    if (!b->configured && wl_display_roundtrip(b->display)<0) return 0;
    return b->configured && !b->closed && flush(b);
}
int tb_present(struct bridge *b, const void *pixels, int w, int h, int scale) {
    if (!b || !b->layer || !b->configured || b->closed || !pixels ||
        w<=0 || h<=0 || w>16384 || h>16384 || scale<1 || !tb_dispatch(b)) return 0;
    struct buffer *slot=NULL;
    for (int i=0;i<3;i++) if (!b->buffers[i].busy) {slot=&b->buffers[i];break;}
    if (!slot) return 1; /* The compositor owns all buffers: drop this frame. */
    if (slot->width!=w || slot->height!=h) {
        buffer_destroy(slot);if (!buffer_create(b,slot,w,h)) return 0;
    }
    memcpy(slot->pixels,pixels,slot->size);slot->busy=1;
    wl_surface_set_buffer_scale(b->surface,scale);
    wl_surface_attach(b->surface,slot->object,0,0);
    wl_surface_damage_buffer(b->surface,0,0,w,h);
    wl_surface_commit(b->surface);return flush(b);
}
int tb_next_event(struct bridge *b, int *kind, int *x, int *y) {
    if (!b || b->read_event==b->write_event) return 0;
    struct event *e=&b->events[b->read_event];*kind=e->kind;*x=e->x;*y=e->y;
    b->read_event=(b->read_event+1)%EVENT_COUNT;return 1;
}
void tb_close(struct bridge *b) {
    if (!b) return;
    if (b->display) {
        if (b->keyboard) {
            int had_keys=0;
            for (uint32_t i=0;i<768;i++) if (b->held[i]) {
                zwp_virtual_keyboard_v1_key(b->keyboard,timestamp(),i,0);had_keys=1;
            }
            if (had_keys) zwp_virtual_keyboard_v1_modifiers(b->keyboard,0,0,0,0);
            zwp_virtual_keyboard_v1_destroy(b->keyboard);
        }
        if (b->virtual_pointer) {
            for (uint32_t i=0;i<2;i++) if (b->buttons & (1u<<i))
                zwlr_virtual_pointer_v1_button(b->virtual_pointer,timestamp(),0x110+i,0);
            if (b->buttons) zwlr_virtual_pointer_v1_frame(b->virtual_pointer);
            zwlr_virtual_pointer_v1_destroy(b->virtual_pointer);
        }
        tb_hide(b);
        for (int i=0;i<3;i++) buffer_destroy(&b->buffers[i]);
        if (b->cursor_surface) wl_surface_destroy(b->cursor_surface);
        buffer_destroy(&b->cursor_buffer);
        if (b->pointer) wl_pointer_release(b->pointer);
        for (int i=0;i<b->output_count;i++) wl_output_release(b->outputs[i].object);
        if (b->seat) wl_seat_release(b->seat);
        if (b->shell) wl_proxy_destroy((struct wl_proxy *)b->shell); /* destroy request needs v3 */
        if (b->pointer_manager) zwlr_virtual_pointer_manager_v1_destroy(b->pointer_manager);
        if (b->keyboard_manager) wl_proxy_destroy((struct wl_proxy *)b->keyboard_manager);
        if (b->shm) wl_shm_destroy(b->shm);
        if (b->compositor) wl_compositor_destroy(b->compositor);
        if (b->registry) wl_registry_destroy(b->registry);
        wl_display_flush(b->display);wl_display_disconnect(b->display);
    }
    if (b->state) xkb_state_unref(b->state);
    if (b->keymap) xkb_keymap_unref(b->keymap);
    if (b->xkb) xkb_context_unref(b->xkb);
    free(b);
}
