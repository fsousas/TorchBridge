"""Read-only fd transfer: kernel peer identity, PID reuse and descriptor lifetime."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux Unix descriptor handoff")
class MemoryHandoffTests(unittest.TestCase):
    def setUp(self):
        from torchbridge.memory_handoff import MemoryHandoff
        self.broker=MemoryHandoff();self.addCleanup(self.broker.close)

    def child(self, *, writable=False, ordinary=False, magic="TBMEMFD1"):
        code=r"""
import array,ctypes,os,socket,sys
ctypes.CDLL(None).prctl(15,b"Torchlight.exe",0,0,0)
buffer=ctypes.create_string_buffer(b"TB-read-only-fixture")
print(ctypes.addressof(buffer),flush=True)
channel=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
channel.connect(sys.argv[1])
fd=os.open("/dev/null" if sys.argv[3]=="1" else "/proc/self/mem",
           os.O_RDWR if sys.argv[2]=="1" else os.O_RDONLY)
channel.sendmsg([sys.argv[4].encode()],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array("i",[fd]))])
os.close(fd);channel.shutdown(socket.SHUT_WR);channel.recv(1);channel.close()
print("SENT",flush=True)
sys.stdin.read()
"""
        child=subprocess.Popen([sys.executable,"-c",code,self.broker.address,str(int(writable)),
                                str(int(ordinary)),magic],
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        address=int(child.stdout.readline())
        def stop():
            if child.poll() is None:
                child.stdin.close()
                child.wait(timeout=3)
            child.stdout.close()
        self.addCleanup(stop)
        return child,address

    def test_permission_failure_uses_the_game_supplied_read_only_fd(self):
        from torchbridge.linux_process import LinuxProcess,process_start
        from torchbridge import memory_handoff
        child,address=self.child()
        start=process_start(child.pid);deadline=time.monotonic()+2
        while child.pid not in self.broker.descriptors and time.monotonic()<deadline:
            time.sleep(.01)
        process=LinuxProcess();self.addCleanup(process.close)
        with patch.object(memory_handoff,"_broker",self.broker), \
             patch("torchbridge.linux_process.os.open",side_effect=PermissionError):
            self.assertTrue(process.attach(child.pid))
        self.assertEqual(process.read(address,20),b"TB-read-only-fixture")
        self.assertIsNone(self.broker.descriptor(child.pid,"reused PID"))
        process.close()
        duplicate=self.broker.descriptor(child.pid,start)
        self.assertIsNotNone(duplicate)
        self.assertEqual(os.pread(duplicate,20,address),b"TB-read-only-fixture")
        with self.assertRaises(OSError):os.pwrite(duplicate,b"BAD",address)
        os.close(duplicate)
        child.stdin.close();child.wait(timeout=3)
        self.broker._expire()
        self.assertNotIn(child.pid,self.broker.descriptors)

    def test_writable_foreign_files_and_invalid_magic_are_rejected(self):
        for options in ({"writable":True},{"ordinary":True},{"magic":"BADMAGIC"}):
            child,_=self.child(**options)
            self.assertEqual(child.stdout.readline().strip(),"SENT")
            # The receiver has closed its peer, and the sender remains alive.
            self.assertNotIn(child.pid,self.broker.descriptors)
            child.stdin.close();child.wait(timeout=3)
            self.broker._expire()
            self.assertNotIn(child.pid,self.broker.descriptors)

    def test_host_record_is_private_and_removed_only_if_still_owned(self):
        from torchbridge.memory_handoff import HOST,HOST_FILE,MAGIC
        with tempfile.TemporaryDirectory() as directory:
            exe=Path(directory)/"Torchlight.exe"
            self.broker.publish(exe)
            record=exe.parent/HOST_FILE
            values=HOST.unpack(record.read_bytes())
            self.assertEqual(values[:3],(MAGIC,1,os.getpid()))
            self.assertEqual(record.stat().st_mode & 0o777,0o600)
            self.broker.close()
            self.assertFalse(record.exists())

    def test_existing_unmanaged_host_record_is_preserved(self):
        from torchbridge.memory_handoff import HOST_FILE
        with tempfile.TemporaryDirectory() as directory:
            exe=Path(directory)/"Torchlight.exe"
            target=exe.parent/HOST_FILE;target.write_bytes(b"other application")
            with self.assertRaises(FileExistsError):self.broker.publish(exe)
            self.assertEqual(target.read_bytes(),b"other application")
