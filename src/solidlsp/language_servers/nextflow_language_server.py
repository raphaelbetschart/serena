"""
Provides Nextflow specific instantiation of the LanguageServer class. Contains various configurations and settings specific to Nextflow.
"""

import dataclasses
import logging
import os
import pathlib
import shlex

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import Language, LanguageServerConfig
from solidlsp.ls_utils import FileUtils, PlatformUtils
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings

log = logging.getLogger(__name__)


@dataclasses.dataclass
class NextflowRuntimeDependencyPaths:
    """
    Stores the paths to the runtime dependencies of Nextflow Language Server
    """

    java_path: str
    java_home_path: str
    ls_jar_path: str
    nextflow_home_path: str | None = None


class NextflowLanguageServer(SolidLanguageServer):
    """
    Provides Nextflow specific instantiation of the LanguageServer class.
    Contains various configurations and settings specific to Nextflow.
    """

    def __init__(self, config: LanguageServerConfig, repository_root_path: str, solidlsp_settings: SolidLSPSettings):
        """
        Creates a Nextflow Language Server instance. This class is not meant to be instantiated directly. Use LanguageServer.create() instead.
        """
        runtime_dependency_paths = self._setup_runtime_dependencies(solidlsp_settings)
        self.runtime_dependency_paths = runtime_dependency_paths

        # Get jar options from configuration
        ls_jar_options = []

        if solidlsp_settings.ls_specific_settings:
            nextflow_settings = solidlsp_settings.get_ls_specific_settings(Language.NEXTFLOW)
            jar_options_str = nextflow_settings.get("ls_jar_options", "")
            if jar_options_str:
                ls_jar_options = shlex.split(jar_options_str)
                log.info(f"Using Nextflow LS JAR options from configuration: {jar_options_str}")

        # Create command to execute the Nextflow Language Server
        cmd = [self.runtime_dependency_paths.java_path, "-jar", self.runtime_dependency_paths.ls_jar_path]
        cmd.extend(ls_jar_options)

        # Set environment variables including JAVA_HOME
        proc_env = {"JAVA_HOME": self.runtime_dependency_paths.java_home_path}

        super().__init__(
            config,
            repository_root_path,
            ProcessLaunchInfo(cmd=cmd, env=proc_env, cwd=repository_root_path),
            "nextflow",
            solidlsp_settings,
        )

        log.info(f"Starting Nextflow Language Server with jar options: {ls_jar_options}")

    @classmethod
    def _setup_runtime_dependencies(cls, solidlsp_settings: SolidLSPSettings) -> NextflowRuntimeDependencyPaths:
        """
        Setup runtime dependencies for Nextflow Language Server and return paths.
        """
        platform_id = PlatformUtils.get_platform_id()

        # Verify platform support
        assert (
            platform_id.value.startswith("win-") or platform_id.value.startswith("linux-") or platform_id.value.startswith("osx-")
        ), "Only Windows, Linux and macOS platforms are supported for Nextflow in multilspy at the moment"

        # Check if user specified custom Java home path
        java_home_path = None
        java_path = None

        if solidlsp_settings and solidlsp_settings.ls_specific_settings:
            nextflow_settings = solidlsp_settings.get_ls_specific_settings(Language.NEXTFLOW)
            custom_java_home = nextflow_settings.get("ls_java_home_path")
            if custom_java_home:
                log.info(f"Using custom Java home path from configuration: {custom_java_home}")
                java_home_path = custom_java_home

                # Determine java executable path based on platform
                if platform_id.value.startswith("win-"):
                    java_path = os.path.join(java_home_path, "bin", "java.exe")
                else:
                    java_path = os.path.join(java_home_path, "bin", "java")

        # If no custom Java home path, download and use bundled Java
        if java_home_path is None:
            # Runtime dependency information
            runtime_dependencies = {
                "java": {
                    "win-x64": {
                        "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-win32-x64-1.42.0-561.vsix",
                        "archiveType": "zip",
                        "java_home_path": "extension/jre/21.0.7-win32-x86_64",
                        "java_path": "extension/jre/21.0.7-win32-x86_64/bin/java.exe",
                    },
                    "linux-x64": {
                        "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-linux-x64-1.42.0-561.vsix",
                        "archiveType": "zip",
                        "java_home_path": "extension/jre/21.0.7-linux-x86_64",
                        "java_path": "extension/jre/21.0.7-linux-x86_64/bin/java",
                    },
                    "linux-arm64": {
                        "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-linux-arm64-1.42.0-561.vsix",
                        "archiveType": "zip",
                        "java_home_path": "extension/jre/21.0.7-linux-aarch64",
                        "java_path": "extension/jre/21.0.7-linux-aarch64/bin/java",
                    },
                    "osx-x64": {
                        "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-darwin-x64-1.42.0-561.vsix",
                        "archiveType": "zip",
                        "java_home_path": "extension/jre/21.0.7-macosx-x86_64",
                        "java_path": "extension/jre/21.0.7-macosx-x86_64/bin/java",
                    },
                    "osx-arm64": {
                        "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-darwin-arm64-1.42.0-561.vsix",
                        "archiveType": "zip",
                        "java_home_path": "extension/jre/21.0.7-macosx-aarch64",
                        "java_path": "extension/jre/21.0.7-macosx-aarch64/bin/java",
                    },
                },
            }

            java_dependency = runtime_dependencies["java"][platform_id.value]

            static_dir = os.path.join(cls.ls_resources_dir(solidlsp_settings), "nextflow_language_server")
            os.makedirs(static_dir, exist_ok=True)

            java_dir = os.path.join(static_dir, "java")
            os.makedirs(java_dir, exist_ok=True)

            java_home_path = os.path.join(java_dir, java_dependency["java_home_path"])
            java_path = os.path.join(java_dir, java_dependency["java_path"])

            if not os.path.exists(java_path):
                log.info(f"Downloading Java for {platform_id.value}...")
                FileUtils.download_and_extract_archive(java_dependency["url"], java_dir, java_dependency["archiveType"])

                if not platform_id.value.startswith("win-"):
                    os.chmod(java_path, 0o755)

        assert java_path and os.path.exists(java_path), f"Java executable not found at {java_path}"

        ls_jar_path = cls._find_nextflow_ls_jar(solidlsp_settings)

        return NextflowRuntimeDependencyPaths(java_path=java_path, java_home_path=java_home_path, ls_jar_path=ls_jar_path)

    @classmethod
    def _find_nextflow_ls_jar(cls, solidlsp_settings: SolidLSPSettings) -> str:
        """
        Find Nextflow Language Server JAR file
        """
        if solidlsp_settings and solidlsp_settings.ls_specific_settings:
            nextflow_settings = solidlsp_settings.get_ls_specific_settings(Language.NEXTFLOW)
            config_jar_path = nextflow_settings.get("ls_jar_path")
            if config_jar_path and os.path.exists(config_jar_path):
                log.info(f"Using Nextflow LS JAR from configuration: {config_jar_path}")
                return config_jar_path

        # if JAR not found
        raise RuntimeError(
            "Nextflow Language Server JAR not found. To use Nextflow language support:\n"
            "Set 'ls_jar_path' in nextflow settings in serena_config.yml:\n"
            "   ls_specific_settings:\n"
            "     nextflow:\n"
            "       ls_jar_path: '/path/to/nextflow-language-server.jar'\n"
            "   Ensure the JAR file is available at the configured path\n"
        )

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Returns the initialize params for the Nextflow Language Server.
        """
        if not os.path.isabs(repository_absolute_path):
            repository_absolute_path = os.path.abspath(repository_absolute_path)

        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        initialize_params = {
            "clientInfo": {"name": "Serena Nextflow Client", "version": "1.0.0"},
            "rootPath": repository_absolute_path,
            "rootUri": root_uri,
            "capabilities": {
                "textDocument": {
                    "synchronization": {"dynamicRegistration": True, "didSave": True},
                    "completion": {"dynamicRegistration": True},
                    "hover": {"dynamicRegistration": True, "contentFormat": ["markdown", "plaintext"]},
                    "definition": {"dynamicRegistration": True},
                    "references": {"dynamicRegistration": True},
                    "documentSymbol": {"dynamicRegistration": True},
                    "workspaceSymbol": {"dynamicRegistration": True},
                    "signatureHelp": {"dynamicRegistration": True},
                    "rename": {"dynamicRegistration": True},
                },
                "workspace": {
                    "workspaceFolders": True,
                },
            },
            "initializationOptions": {
                "settings": {
                    "nextflow": {
                        "classpath": [],
                        "diagnostics": {"enabled": True},
                        "completion": {"enabled": True},
                    }
                },
            },
            "processId": os.getpid(),
            "workspaceFolders": [
                {
                    "uri": root_uri,
                    "name": os.path.basename(repository_absolute_path),
                }
            ],
        }
        return initialize_params  # type: ignore

    def _start_server(self) -> None:
        """
        Starts the Nextflow Language Server
        """

        def execute_client_command_handler(params: dict) -> list:
            return []

        def do_nothing(params: dict) -> None:
            return

        def window_log_message(msg: dict) -> None:
            log.info(f"LSP: window/logMessage: {msg}")

        self.server.on_request("client/registerCapability", do_nothing)
        self.server.on_notification("language/status", do_nothing)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_request("workspace/executeClientCommand", execute_client_command_handler)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)
        self.server.on_notification("language/actionableNotification", do_nothing)

        log.info("Starting Nextflow server process")
        self.server.start()
        initialize_params = self._get_initialize_params(self.repository_root_path)

        log.info("Sending initialize request from LSP client to LSP server and awaiting response")
        init_response = self.server.send.initialize(initialize_params)

        capabilities = init_response["capabilities"]
    
        print(capabilities)

        assert "textDocumentSync" in capabilities, "Server must support textDocumentSync"
        assert "hoverProvider" in capabilities, "Server must support hover"
        assert "completionProvider" in capabilities, "Server must support code completion"
        assert "signatureHelpProvider" in capabilities, "Server must support signature help"
        assert "definitionProvider" in capabilities, "Server must support go to definition"
        assert "referencesProvider" in capabilities, "Server must support find references"
        assert "documentSymbolProvider" in capabilities, "Server must support document symbols"
        assert "workspaceSymbolProvider" in capabilities, "Server must support workspace symbols"

        self.server.notify.initialized({})
