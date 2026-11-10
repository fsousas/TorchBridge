"""Real loopback framing/lifecycle and reversible native module installation."""
import socket
import struct
import tempfile
import threading
import time
import unittest
from concurrent.futures import Future
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from torchbridge.native_input import (NativeInputClient, MAGIC, VERSION, ENDPOINT, COMMAND,
                                      REPLY, ACTIVE, DIRECT, WALKING)
from torchbridge.native_input_setup import (IDENTITY, MANIFEST, install, remove,
                                            launch_environment)
from test_fullscreen import pe_file
from torchbridge.memory import TorchlightMemoryReader
from test_world_memory import AddressSpace


class NativeExportDiscoveryTests(unittest.TestCase):
    def fixture(self,base=0x73000000):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        proc=Path(temp.name);(proc/"42").mkdir()
        (proc/"42/maps").write_text(f"{base:x}-{base+4096:x} r--p 00000000 00:00 0 /pfx/winmm.dll\n")
        data=bytearray(4096)
        data[:2]=b"MZ";struct.pack_into("<I",data,60,64)
        data[64:68]=b"PE\0\0";struct.pack_into("<H",data,88,0x10B)
        struct.pack_into("<II",data,184,0x400,0x100)
        struct.pack_into("<5I",data,0x400+20,1,1,0x510,0x500,0x520)
        struct.pack_into("<I",data,0x500,0x600)
        struct.pack_into("<I",data,0x510,0x800)
        data[0x600:0x600+25]=b"TorchBridgeInputEndpoint\0"
        space=AddressSpace();space.put(base,data)
        memory=TorchlightMemoryReader();memory._handle=1;memory.pid=42
        memory._linux=SimpleNamespace(proc=proc,read=space.read)
        return memory,space,base

    def test_endpoint_is_resolved_from_the_selected_relocated_process(self):
        memory,space,base=self.fixture()
        self.assertEqual(memory.find_export("winmm.dll","TorchBridgeInputEndpoint"),base+0x800)
        self.assertIsNone(memory.find_export("winmm.dll","Missing"))

    def test_corrupt_export_counts_and_forwarded_addresses_are_rejected(self):
        memory,space,base=self.fixture()
        space.u32(base+0x510,0x450)
        self.assertIsNone(memory.find_export("winmm.dll","TorchBridgeInputEndpoint"))
        space.u32(base+0x400+24,100000)
        self.assertIsNone(memory.find_export("winmm.dll","TorchBridgeInputEndpoint"))


class LoopbackInputTests(unittest.TestCase):
    def setUp(self):
        self.listener=socket.socket()
        self.listener.bind(("127.0.0.1",0))
        self.listener.listen()
        self.listener.settimeout(2)
        self.frames=[]
        self.stop=threading.Event()
        self.peer=None
        self.secret=b"1234567890123456"
        self.corrupt=False
        self.thread=threading.Thread(target=self.serve,daemon=True)
        self.thread.start()
        self.client=NativeInputClient()
        raw=ENDPOINT.pack(MAGIC,VERSION,self.listener.getsockname()[1],self.secret,0x100,0x400000,7,0)
        self.memory=SimpleNamespace(pid=9876,_module_base=0x400000,_linux=SimpleNamespace(start="1"),
                                    find_export=lambda *_:0x800000,read_bytes=lambda *_:raw)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.stop.set()
        self.client.close()
        if self.peer:
            self.peer.close()
        self.listener.close()
        self.thread.join(timeout=3)

    def serve(self):
        try:
            peer,_=self.listener.accept()
            self.peer=peer;peer.settimeout(.2)
            peer.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            pending=bytearray()
            while not self.stop.is_set():
                try:data=peer.recv(4096)
                except socket.timeout:continue
                if not data:break
                pending.extend(data)
                while len(pending)>=COMMAND.size:
                    frame=COMMAND.unpack(pending[:COMMAND.size]);del pending[:COMMAND.size]
                    self.frames.append(frame)
                    magic=b"BADFRAME" if self.corrupt else MAGIC
                    reply=REPLY.pack(magic,VERSION,frame[2],17,0,0x200000,0,0,2,
                                     1.5,2.5,0,0,0,10)
                    peer.sendall(reply[:13])
                    peer.sendall(reply[13:])
        except OSError:
            pass

    def pump(self, flags=ACTIVE|DIRECT, **kwargs):
        self.client.connect(self.memory,time.monotonic())
        self.client.send(flags=flags,player=0x300000,level=0x100000,**kwargs)

    def until(self,predicate):
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            self.pump()
            if predicate():return
            time.sleep(.01)
        self.fail("Native input loopback did not reach the expected state")

    def test_fragmented_reply_and_pid_translation_are_supported(self):
        self.until(lambda:self.client.ready)
        self.assertEqual(self.frames[0][3],self.secret)
        self.assertEqual(self.client.status.selected,0x200000)
        self.assertEqual(self.client.status.destination_x,1.5)

    def test_action_is_a_sequence_not_a_repeated_button(self):
        self.until(lambda:self.client.ready)
        self.client.interact()
        self.until(lambda:sum(f[-2]==1 for f in self.frames)>=3)
        actions=[f[-2] for f in self.frames]
        self.assertEqual(actions[0],0)
        self.assertEqual(set(actions),{0,1})
        self.assertTrue(all(action==1 for action in actions[actions.index(1):]))
        self.assertEqual(self.client._action,1)

    def test_invalid_movement_closes_transport_instead_of_sending(self):
        self.until(lambda:self.client.ready)
        self.client._last_send=time.monotonic()+1
        self.pump(flags=ACTIVE|DIRECT|WALKING,dx=float("nan"))
        self.assertIsNone(self.client.socket)
        self.assertFalse(any(f[7]!=f[7] for f in self.frames))

    def test_corrupt_protocol_disconnects_and_clears_highlight_state(self):
        self.until(lambda:self.client.ready)
        self.corrupt=True
        deadline=time.monotonic()+1
        while self.client.socket is not None and time.monotonic()<deadline:
            self.client.send(flags=ACTIVE,player=0,level=0)
            time.sleep(.01)
        self.assertIsNone(self.client.socket)
        self.assertEqual(self.client.status.selected,0)

    def test_expired_reply_closes_connection(self):
        self.until(lambda:self.client.ready)
        self.stop.set()
        self.thread.join(timeout=1)
        self.assertFalse(self.thread.is_alive())
        # Replies already in the OS receive queue may still arrive after the
        # peer stops. Drain them through the client, then let its real deadline
        # expire instead of assuming that TCP delivered everything immediately.
        deadline=time.monotonic()+2
        while self.client.socket is not None and time.monotonic()<deadline:
            self.client.send(flags=ACTIVE,player=0,level=0)
            time.sleep(.01)
        self.assertIsNone(self.client.socket)

    def test_frozen_game_frames_do_not_report_ready_despite_network_replies(self):
        self.until(lambda:self.client.ready)
        self.client._frame_at=time.monotonic()-.3
        self.assertFalse(self.client.ready)

    def test_action_age_is_sent_separately_from_the_packet_heartbeat(self):
        self.until(lambda:self.client.ready)
        self.client.interact()
        self.client._action_at-=1
        self.until(lambda:any(f[-2]==1 for f in self.frames))
        self.assertGreaterEqual(next(f[-1] for f in self.frames if f[-2]==1),1000)

    def test_process_identity_change_cancels_the_old_channel(self):
        self.until(lambda:self.client.ready)
        self.memory.pid+=1
        self.memory.find_export=lambda *_:None
        self.client.connect(self.memory,time.monotonic())
        self.assertIsNone(self.client.socket)
        self.assertFalse(self.client.ready)

    def test_missing_loaded_module_is_prepared_once_and_requests_restart(self):
        self.memory.find_export=lambda *_:None
        self.memory._exe_path="/games/Torchlight.exe"
        future=Future()
        with patch("torchbridge.game_setup.prepare_async",return_value=future) as prepare:
            self.client.connect(self.memory,10)
            self.assertIn("Preparando",self.client.message)
            future.set_result([Path(self.memory._exe_path)])
            self.client.connect(self.memory,11)
            self.client.connect(self.memory,12)
        prepare.assert_called_once_with(exe=self.memory._exe_path)
        self.assertIn("Reinicie o Torchlight",self.client.message)
        self.assertNotIn("Instale",self.client.message)

    def test_failed_preparation_reports_the_actual_conflict(self):
        self.memory.find_export=lambda *_:None
        self.memory._exe_path="/games/Torchlight.exe"
        future=Future();future.set_exception(FileExistsError("Outro módulo usa winmm.dll"))
        with patch("torchbridge.game_setup.prepare_async",return_value=future):
            self.client.connect(self.memory,10)
        self.assertEqual(self.client.message,"Outro módulo usa winmm.dll")


class NativeInputInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.game=self.root/"Torchlight.exe"
        data=bytearray(pe_file());struct.pack_into("<I",data,72,0x4B5F7519)
        self.game.write_bytes(data)
        self.source=self.root/"source.dll"
        self.source.write_bytes(pe_file(dll=True)+IDENTITY)

    def test_install_remove_preserves_game_saves_and_other_overlay(self):
        before=self.game.read_bytes()
        (self.root/"d3d9.dll").write_bytes(b"other overlay")
        (self.root/"save.svt").write_bytes(b"save")
        target=install(self.game,self.source)
        self.assertEqual(target.read_bytes(),self.source.read_bytes())
        self.assertTrue((self.root/MANIFEST).exists())
        remove(self.game)
        self.assertFalse(target.exists())
        self.assertEqual(self.game.read_bytes(),before)
        self.assertEqual((self.root/"save.svt").read_bytes(),b"save")
        self.assertEqual((self.root/"d3d9.dll").read_bytes(),b"other overlay")

    def test_existing_mod_and_modified_managed_dll_are_not_overwritten(self):
        mod=self.root/"WINMM.DLL";mod.write_bytes(b"mod")
        with self.assertRaises(FileExistsError):install(self.game,self.source)
        mod.unlink()
        target=install(self.game,self.source);target.write_bytes(target.read_bytes()+b"modified")
        with self.assertRaises(ValueError):remove(self.game)
        self.assertTrue(target.exists())
        with self.assertRaises(ValueError):install(self.game,self.source)

    def test_repeating_installation_keeps_the_existing_managed_module(self):
        target=install(self.game,self.source)
        before=(target.stat().st_mtime_ns,(self.root/MANIFEST).read_bytes())
        self.assertEqual(install(self.game,self.source),target)
        self.assertEqual((target.stat().st_mtime_ns,(self.root/MANIFEST).read_bytes()),before)

    def test_update_of_an_intact_managed_module_preserves_activation_record(self):
        import json
        target=install(self.game,self.source)
        record=json.loads((self.root/MANIFEST).read_text())
        record["wine"]={"prefix":"/games/prefix","previous":"builtin"}
        (self.root/MANIFEST).write_text(json.dumps(record))
        self.source.write_bytes(self.source.read_bytes()+b"new build")
        install(self.game,self.source)
        self.assertEqual(target.read_bytes(),self.source.read_bytes())
        current=json.loads((self.root/MANIFEST).read_text())
        self.assertEqual(current["wine"],record["wine"])
        self.assertNotEqual(current["sha256"],record["sha256"])

    def test_failed_record_update_restores_previous_dll(self):
        target=install(self.game,self.source)
        before=target.read_bytes();record=(self.root/MANIFEST).read_bytes()
        self.source.write_bytes(self.source.read_bytes()+b"new build")
        with patch("torchbridge.native_input_setup.write_record",side_effect=OSError("disk full")):
            with self.assertRaises(OSError):install(self.game,self.source)
        self.assertEqual(target.read_bytes(),before)
        self.assertEqual((self.root/MANIFEST).read_bytes(),record)

    def test_unknown_game_build_is_rejected(self):
        self.game.write_bytes(pe_file())
        with self.assertRaises(ValueError):install(self.game,self.source)
        self.assertFalse((self.root/"winmm.dll").exists())

    def test_wine_override_preserves_unrelated_and_grouped_entries(self):
        env={"WINEDLLOVERRIDES":"winmm,d3d9=n;xaudio2_7=b"}
        result=launch_environment(env)
        self.assertEqual(result["WINEDLLOVERRIDES"],"d3d9=n;xaudio2_7=b;winmm=n,b")
        self.assertEqual(env["WINEDLLOVERRIDES"],"winmm,d3d9=n;xaudio2_7=b")
