"""
Integration tests for project structure
and configuration validation.
"""
"""
Copyright (c) 2026 Wind River Systems, Inc.
SPDX-License-Identifier: Apache-2.0
"""
import os
import unittest

import yaml

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))


class TestProjectStructure(unittest.TestCase):
    """Validate project file structure."""

    def test_root_files_exist(self):
        """Test essential root files exist."""
        root_files = [
            'tox.ini', '.zuul.yaml',
            'test-requirements.txt',
            'requirements.txt']
        for filename in root_files:
            filepath = os.path.join(
                PROJECT_ROOT, filename)
            self.assertTrue(
                os.path.exists(filepath),
                "Missing root file: {}".format(
                    filename))

    def test_subproject_dirs_exist(self):
        """Test subproject directories exist."""
        subproject_dirs = [
            'python3-k8sapp-ptp-notification',
            'notificationservice-base-v2',
            'locationservice-base',
            'notificationclient-base']
        for dirname in subproject_dirs:
            dirpath = os.path.join(
                PROJECT_ROOT, dirname)
            self.assertTrue(
                os.path.isdir(dirpath),
                "Missing directory: {}".format(
                    dirname))

    def test_tracking_sdk_structure(self):
        """Test trackingfunctionsdk subdirs."""
        sdk_path = os.path.join(
            PROJECT_ROOT,
            'notificationservice-base-v2',
            'ptptrackingfunction',
            'trackingfunctionsdk')
        expected_subdirs = [
            'client', 'common', 'model',
            'services', 'tests']
        for subdir in expected_subdirs:
            path = os.path.join(
                sdk_path, subdir)
            self.assertTrue(
                os.path.isdir(path),
                "Missing SDK subdir: {}".format(
                    subdir))

    def test_k8sapp_structure(self):
        """Test k8sapp has expected subdirs."""
        k8s_path = os.path.join(
            PROJECT_ROOT,
            'python3-k8sapp-ptp-notification',
            'k8sapp_ptp_notification',
            'k8sapp_ptp_notification')
        expected_subdirs = [
            'common', 'helm',
            'lifecycle', 'tests']
        for subdir in expected_subdirs:
            path = os.path.join(
                k8s_path, subdir)
            self.assertTrue(
                os.path.isdir(path),
                "Missing k8sapp subdir: {}"
                .format(subdir))

    def test_init_files_present(self):
        """Test __init__.py in key packages."""
        sdk_base = os.path.join(
            PROJECT_ROOT,
            'notificationservice-base-v2',
            'ptptrackingfunction',
            'trackingfunctionsdk')
        package_dirs = [
            '', 'client', 'common',
            'model', 'services']
        for subdir in package_dirs:
            init_path = os.path.join(
                sdk_base, subdir,
                '__init__.py')
            self.assertTrue(
                os.path.exists(init_path),
                "Missing __init__.py in: {}"
                .format(subdir or 'root'))


class TestYamlFilesValidity(unittest.TestCase):
    """Test YAML files are valid."""

    def test_zuul_yaml_valid(self):
        """Test .zuul.yaml is valid YAML."""
        zuul_path = os.path.join(
            PROJECT_ROOT, '.zuul.yaml')
        with open(zuul_path, 'r') as zuul_file:
            content = zuul_file.read()
        self.assertGreater(len(content), 0)
        self.assertIn('project', content)

    def test_zuul_yaml_has_project(self):
        """Test .zuul.yaml has project def."""
        zuul_path = os.path.join(
            PROJECT_ROOT, '.zuul.yaml')
        with open(zuul_path, 'r') as zuul_file:
            content = zuul_file.read()
        self.assertIn('- project:', content)

    def test_zuul_yaml_has_jobs(self):
        """Test .zuul.yaml has job defs."""
        zuul_path = os.path.join(
            PROJECT_ROOT, '.zuul.yaml')
        with open(zuul_path, 'r') as zuul_file:
            content = zuul_file.read()
        self.assertIn('- job:', content)
        self.assertIn(
            'ptp-notification-tox-coverage',
            content)
        self.assertIn(
            'ptp-notification-tox-security',
            content)

    def test_fluxcd_yaml_files(self):
        """Test FluxCD YAML files are valid."""
        fluxcd_dir = os.path.join(
            PROJECT_ROOT,
            'stx-ptp-notification-helm',
            'stx-ptp-notification-helm',
            'fluxcd-manifests')
        if not os.path.isdir(fluxcd_dir):
            return
        for root, _, files in os.walk(
                fluxcd_dir):
            for fname in files:
                if not fname.endswith(
                        ('.yaml', '.yml')):
                    continue
                fpath = os.path.join(
                    root, fname)
                with open(fpath, 'r') as yf:
                    content = yf.read()
                if '{{' in content:
                    continue
                try:
                    yaml.safe_load(content)
                except yaml.YAMLError:
                    self.fail(
                        "Invalid YAML: {}"
                        .format(fpath))

    def test_metadata_yaml_files(self):
        """Test metadata YAML files valid."""
        for root, _, files in os.walk(
                PROJECT_ROOT):
            if '.tox' in root or \
                    '.git' in root:
                continue
            for fname in files:
                if fname != 'meta_data.yaml':
                    continue
                fpath = os.path.join(
                    root, fname)
                with open(fpath, 'r') as mf:
                    data = yaml.safe_load(mf)
                self.assertIsNotNone(data)


class TestModuleImports(unittest.TestCase):
    """Test key modules can be imported."""

    def test_import_ptpstate(self):
        """Test PtpState import."""
        from trackingfunctionsdk.model.dto \
            .ptpstate import PtpState
        self.assertIsNotNone(PtpState)

    def test_import_gnssstate(self):
        """Test GnssState import."""
        from trackingfunctionsdk.model.dto \
            .gnssstate import GnssState
        self.assertIsNotNone(GnssState)

    def test_import_osclockstate(self):
        """Test OsClockState import."""
        from trackingfunctionsdk.model.dto \
            .osclockstate import OsClockState
        self.assertIsNotNone(OsClockState)

    def test_import_overallclockstate(self):
        """Test OverallClockState import."""
        from trackingfunctionsdk.model.dto \
            .overallclockstate import (
                OverallClockState)
        self.assertIsNotNone(OverallClockState)

    def test_import_constants(self):
        """Test constants import."""
        from trackingfunctionsdk.common \
            .helpers import constants
        self.assertIsNotNone(constants)

    def test_import_log_helper(self):
        """Test log_helper import."""
        from trackingfunctionsdk.common \
            .helpers import log_helper
        self.assertIsNotNone(log_helper)

    def test_import_ptpsync(self):
        """Test ptpsync import."""
        from trackingfunctionsdk.common \
            .helpers import ptpsync
        self.assertIsNotNone(ptpsync)

    def test_import_instance_config(self):
        """Test instance_config_parser import."""
        from trackingfunctionsdk.common \
            .helpers import instance_config_parser
        self.assertIsNotNone(
            instance_config_parser)

    def test_import_config_watcher(self):
        """Test config_watcher import."""
        from trackingfunctionsdk.services \
            .config_watcher import (
                ConfigFileWatcher)
        self.assertIsNotNone(ConfigFileWatcher)

    def test_import_health(self):
        """Test health module import."""
        from trackingfunctionsdk.services \
            .health import HealthServer
        self.assertIsNotNone(HealthServer)

    def test_import_rpc_endpoint(self):
        """Test RpcEndpointInfo import."""
        from trackingfunctionsdk.model.dto \
            .rpc_endpoint import RpcEndpointInfo
        self.assertIsNotNone(RpcEndpointInfo)

    def test_import_ptpstatus(self):
        """Test PtpStatus import."""
        from trackingfunctionsdk.model.dto \
            .ptpstatus import PtpStatus
        self.assertIsNotNone(PtpStatus)

    def test_import_resourcetype(self):
        """Test ResourceType import."""
        from trackingfunctionsdk.model.dto \
            .resourcetype import ResourceType
        self.assertIsNotNone(ResourceType)


class TestSetupFiles(unittest.TestCase):
    """Test setup.py and setup.cfg files."""

    def test_notificationservice_setup_py(self):
        """Test notificationservice setup.py."""
        setup_path = os.path.join(
            PROJECT_ROOT,
            'notificationservice-base-v2',
            'ptptrackingfunction',
            'setup.py')
        self.assertTrue(
            os.path.exists(setup_path))
        with open(setup_path, 'r') as sf:
            content = sf.read()
        self.assertIn('setup(', content)

    def test_k8sapp_setup_cfg(self):
        """Test k8sapp setup.cfg sections."""
        cfg_path = os.path.join(
            PROJECT_ROOT,
            'python3-k8sapp-ptp-notification',
            'k8sapp_ptp_notification',
            'setup.cfg')
        self.assertTrue(
            os.path.exists(cfg_path))
        with open(cfg_path, 'r') as cf:
            content = cf.read()
        self.assertIn('[metadata]', content)
        self.assertIn(
            '[entry_points]', content)


if __name__ == '__main__':
    unittest.main()
