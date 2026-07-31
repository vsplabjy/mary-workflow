from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_model import configure_deepseek, install_shell_integration, switch_deepseek, switch_vsp  # noqa: E402


class ModelProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.config = root / "config.toml"
        self.state = root / "mary-workflow-model.json"
        self.catalog = root / "models.json"
        self.config.write_text(
            "model_provider = \"vsp_lab_api\"\n"
            "model = \"gpt-5.6-luna\"\n"
            "model_reasoning_effort = \"high\"\n"
            "model_context_window = 1000000\n"
            "model_auto_compact_token_limit = 900000\n"
            "\n"
            "[model_providers.vsp_lab_api]\n"
            "name = \"vsp_lab_api\"\n"
            "base_url = \"https://api.vsplab.cn\"\n"
            "wire_api = \"responses\"\n"
            "\n"
            "[projects.\"/tmp/project\"]\n"
            "trust_level = \"trusted\"\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_configure_keeps_vsp_default_and_places_provider_after_vsp(self) -> None:
        with mock.patch("mw_model.read_deepseek_api_key", return_value="sk-test"):
            configure_deepseek(self.config, self.state, self.catalog)
        text = self.config.read_text(encoding="utf-8")
        self.assertIn('model_provider = "vsp_lab_api"', text)
        self.assertIn('model = "gpt-5.6-luna"', text)
        self.assertLess(text.index("[model_providers.vsp_lab_api]"), text.index("[model_providers.deepseek]"))
        self.assertLess(text.index("[model_providers.deepseek]"), text.index('[projects."/tmp/project"]'))
        self.assertIn('experimental_bearer_token = "sk-test"', text)
        self.assertIn("model_context_window = 1000000", text)
        with self.config.open("rb") as handle:
            parsed = tomllib.load(handle)
        self.assertEqual(parsed["model_provider"], "vsp_lab_api")
        self.assertEqual(parsed["model_providers"]["deepseek"]["wire_api"], "responses")
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        self.assertEqual({item["slug"] for item in catalog["models"]}, {"deepseek-v4-flash", "deepseek-v4-pro"})

    def test_switch_round_trip_restores_vsp_settings(self) -> None:
        with mock.patch("mw_model.read_deepseek_api_key", return_value="sk-test"):
            configure_deepseek(self.config, self.state, self.catalog)
            switch_deepseek(self.config, self.state, self.catalog)
        deepseek_text = self.config.read_text(encoding="utf-8")
        self.assertIn('model_provider = "deepseek"', deepseek_text)
        self.assertIn('model = "deepseek-v4-flash"', deepseek_text)
        self.assertNotIn("model_context_window = 1000000", deepseek_text)

        switch_vsp(self.config, self.state)
        vsp_text = self.config.read_text(encoding="utf-8")
        self.assertIn('model_provider = "vsp_lab_api"', vsp_text)
        self.assertIn('model = "gpt-5.6-luna"', vsp_text)
        self.assertIn("model_context_window = 1000000", vsp_text)
        self.assertIn("model_auto_compact_token_limit = 900000", vsp_text)

    def test_first_init_shell_setup_detects_fish_and_is_idempotent(self) -> None:
        config_root = Path(self.tempdir.name) / "config"
        environment = {"SHELL": "/usr/bin/fish", "XDG_CONFIG_HOME": str(config_root)}
        with mock.patch.dict(os.environ, environment), mock.patch("mw_model.shutil.which", return_value="/usr/bin/fish"):
            first = install_shell_integration()
            second = install_shell_integration()
        completion = (config_root / "fish/completions/mw-model.fish").read_text(encoding="utf-8")
        self.assertIn("shell=fish", first)
        self.assertIn("shell=fish", second)
        self.assertIn("configure", completion)
        self.assertEqual(completion.count("complete -c mw-model"), 2)

    def test_first_init_shell_setup_detects_bash_and_updates_rc_once(self) -> None:
        home = Path(self.tempdir.name) / "home"
        environment = {"SHELL": "/bin/bash", "XDG_CONFIG_HOME": str(home / ".config")}
        with mock.patch.dict(os.environ, environment), mock.patch("mw_model.Path.home", return_value=home):
            install_shell_integration()
            install_shell_integration()
        bashrc = (home / ".bashrc").read_text(encoding="utf-8")
        self.assertEqual(bashrc.count("# >>> mary-workflow mw-model >>>"), 1)
        self.assertIn("complete -F _mw_model_complete mw-model", bashrc)


if __name__ == "__main__":
    unittest.main()
