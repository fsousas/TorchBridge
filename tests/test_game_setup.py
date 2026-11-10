"""Automatic provisioning, Steam discovery and per-game Wine activation."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from torchbridge import game_setup as setup
from torchbridge.native_input_setup import MANIFEST, install, remove
import test_native_input as fixtures


class GamePreparationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.steam=self.root/"Steam Client"
        self.library=self.root/"Other Library"
        self.game=self.library/"steamapps/common/Torchlight"
        self.game.mkdir(parents=True)
        (self.steam/"steamapps").mkdir(parents=True)
        library=str(self.library).replace("\\","\\\\")
        (self.steam/"steamapps/libraryfolders.vdf").write_text(
            '"libraryfolders" { "0" { "path" "'+library+'" } }',encoding="utf-8")
        (self.library/"steamapps/appmanifest_41500.acf").write_text(
            '"AppState" { "appid" "41500" "installdir" "Torchlight" }',encoding="utf-8")
        self.exe=self.game/"Torchlight.exe";self.exe.write_bytes(b"discovery only")
        self.prefix=self.steam/"steamapps/compatdata/41500/pfx"
        self.prefix.mkdir(parents=True)
        self.registry=self.prefix/"user.reg"
        self.registry.write_text('WINE REGISTRY Version 2\n\n[Software\\\\Wine\\\\DllOverrides]\n"winmm"="builtin"\n')
        self.proton=self.root/"GE-Proton/proton"
        self.proton.parent.mkdir();self.proton.write_text("runtime")
        (self.prefix.parent/"config_info").write_text(
            (self.proton.parent/"files/share/default_pfx").as_posix()+"/\n")
        self.environment={"STEAM_COMPAT_CLIENT_INSTALL_PATH":str(self.steam)}
        self.patch=patch.object(setup,"_windows_locations",return_value=([],[]))
        self.patch.start();self.addCleanup(self.patch.stop)

    def discover(self,**kwargs):
        return setup.discover(environment=self.environment,home=self.root/"empty-home",**kwargs)

    def test_other_steam_library_uses_its_manifest_and_existing_client_prefix(self):
        games=self.discover()
        self.assertEqual(len(games),1)
        # Windows TEMP may use an 8.3 alias while discovery resolves Steam's
        # root to its long path. Both must identify the same installation.
        for name,expected in (("exe",self.exe),("prefix",self.prefix),
                              ("proton",self.proton),("steam",self.steam)):
            self.assertTrue(getattr(games[0],name).samefile(expected),name)

    def test_launch_selects_one_game_without_preparing_another_installation(self):
        other=self.root/"GOG/Torchlight.exe";other.parent.mkdir();other.write_bytes(b"other")
        result=self.discover(launch=["wine",str(other)])
        self.assertEqual([game.exe for game in result],[other])

    def test_an_explicit_wine_prefix_is_retained_for_nonsteam_games(self):
        env=dict(self.environment,WINEPREFIX=str(self.prefix))
        with patch.object(setup,"discover",return_value=[]):
            game=setup.for_exe(self.exe,environment=env)
        self.assertEqual(game.prefix,self.prefix)
        self.assertEqual(game.proton,self.proton)

    @unittest.skipIf(os.name=="nt","Wine activation is Linux-only")
    def test_activation_is_specific_to_torchlight_and_records_previous_value(self):
        fixture=fixtures.NativeInputInstallationTests()
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        target=install(fixture.game,fixture.source)
        game=setup.Installation(fixture.game,self.prefix,self.proton,self.steam)
        registry=self.registry.read_bytes()
        with patch.object(setup,"_query",return_value="builtin"), \
             patch.object(setup,"_reg",return_value="") as commands:
            setup.activate_wine(game)
        added=commands.call_args_list[-1].args[1]
        self.assertEqual(added[0],"add")
        self.assertIn(r"HKCU\Software\Wine\AppDefaults\Torchlight.exe\DllOverrides",added)
        self.assertIn("native,builtin",added)
        record=json.loads((target.parent/MANIFEST).read_text())
        self.assertEqual(record["wine"],{"prefix":str(self.prefix.resolve()),"previous":"builtin"})
        self.assertEqual(self.registry.read_bytes(),registry)

    @unittest.skipIf(os.name=="nt","Wine activation is Linux-only")
    def test_existing_activation_needs_no_wine_process(self):
        self.registry.write_text('[Software\\\\Wine\\\\AppDefaults\\\\Torchlight.exe\\\\DllOverrides]\n"winmm"="native,builtin"\n')
        with patch.object(setup,"_reg") as command:
            setup.activate_wine(self.discover()[0])
        command.assert_not_called()

    @unittest.skipIf(os.name=="nt","Wine activation is Linux-only")
    def test_removal_restores_the_previous_override_before_removing_the_module(self):
        fixture=fixtures.NativeInputInstallationTests()
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        target=install(fixture.game,fixture.source)
        record=json.loads((target.parent/MANIFEST).read_text())
        record["wine"]={"prefix":str(self.prefix),"previous":"builtin"}
        (target.parent/MANIFEST).write_text(json.dumps(record))
        calls=[]
        def reg(_game,args,**kwargs):
            self.assertTrue(target.exists())
            calls.append(args)
            return "winmm    REG_SZ    native,builtin\n"
        with patch.object(setup,"_query",return_value="native,builtin"), \
             patch.object(setup,"_reg",side_effect=reg):
            remove(fixture.game)
        self.assertEqual(calls[-1][0],"add")
        self.assertIn("builtin",calls[-1])
        self.assertFalse(target.exists())

    @unittest.skipIf(os.name=="nt","Wine activation is Linux-only")
    def test_external_changes_to_activation_are_preserved_on_removal(self):
        record={"wine":{"prefix":str(self.prefix),"previous":None}}
        with patch.object(setup,"_query",return_value="builtin"), patch.object(setup,"_reg") as reg:
            setup.restore_wine_activation(self.exe,record)
        reg.assert_not_called()

    @unittest.skipIf(os.name=="nt","Wine registry export is Linux-only")
    def test_registry_query_reads_utf16_export_without_depending_on_console_output(self):
        def export(_game,args,**kwargs):
            self.assertEqual(args[0],"export")
            path=Path(args[2][2:].replace("\\","/"))
            path.write_text('Windows Registry Editor Version 5.00\n\n"winmm"="native,builtin"\n',encoding="utf-16")
            return "Proton does not forward reg.exe stdout"
        with patch.object(setup,"_reg",side_effect=export):
            self.assertEqual(setup._query(self.discover()[0]),"native,builtin")

    def test_preparation_installs_before_activating_and_repeating_is_supported(self):
        game=self.discover()[0];steps=[]
        with patch.object(setup,"discover",return_value=[game]), \
             patch.object(setup,"install",side_effect=lambda exe:steps.append(("install",exe))), \
             patch.object(setup,"activate_wine",side_effect=lambda g:steps.append(("activate",g.exe))), \
             patch("torchbridge.memory_handoff.publish"):
            self.assertEqual(setup.prepare(),[self.exe])
            self.assertEqual(setup.prepare(),[self.exe])
        self.assertEqual([kind for kind,_ in steps],["install","activate","install","activate"])

    def test_async_preparation_exposes_conflicts_instead_of_silent_success(self):
        with self.assertLogs(setup.log,level="ERROR"), \
             patch.object(setup,"prepare",side_effect=FileExistsError("other mod")):
            future=setup.prepare_async()
            with self.assertRaisesRegex(FileExistsError,"other mod"):
                future.result(timeout=2)

    @unittest.skipIf(os.name=="nt","Proton invocation is Linux-only")
    def test_registry_tool_uses_the_selected_proton_prefix_and_game_key(self):
        game=self.discover()[0]
        with patch("subprocess.run",return_value=SimpleNamespace(returncode=0,stdout="ok")) as run:
            setup._reg(game,["query",setup._key,"/v","winmm"])
        args=run.call_args
        self.assertEqual(args.args[0][:3],[str(self.proton),"run","reg.exe"])
        self.assertEqual(args.kwargs["env"]["WINEPREFIX"],str(self.prefix))
        self.assertEqual(args.kwargs["env"]["STEAM_COMPAT_CLIENT_INSTALL_PATH"],str(self.steam))
