{
  description = "A self-hosted journal for deliberate trading under uncertainty";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        # Nix platform
        inherit (nixpkgs) lib;
        pkgs = nixpkgs.legacyPackages.${system};

        # Project metadata
        project = fromTOML (builtins.readFile ./pyproject.toml);
        shortRevision = builtins.substring 0 8 self.rev;
        revision = if self ? rev then shortRevision else "dirty";
        version = "${project.project.version}+${revision}";
        packageName = "tradefog-${version}";
        devPackageName = "${packageName}-dev";

        # Container
        imageTag = lib.replaceStrings [ "+" ] [ "-" ] version;
        containerUser = "tradefog";
        containerUid = 1000;
        containerRoot = "/app";

        # Development environment
        developmentSettings = pkgs.writeText "settings.toml" ''
          [application]
          secret_key = "django-insecure-local-development"
          debug = true
          allowed_hosts = ["127.0.0.1", "localhost"]

          [database.sqlite]
          path = "../../data/tradefog/db.sqlite3"

          [logging]
          level = "DEBUG"

          [static]
          root = "../../cache/tradefog/static"

          [media]
          root = "../../data/tradefog/media"
        '';

        # Python workspace
        workspace = uv2nix.lib.workspace.loadWorkspace {
          workspaceRoot = ./.;
        };
        runtimeDeps = workspace.deps.default;
        devDeps = workspace.deps.all;
        workspaceOverlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };
        buildToolsOverlay = final: prev: {
          tradefog = prev.tradefog.overrideAttrs (old: {
            nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [
              pkgs.dart-sass
              pkgs.gettext
            ];
          });
        };
        editableOverlay = workspace.mkEditablePyprojectOverlay {
          root = "$REPO_ROOT";
        };

        pythonSet =
          (pkgs.callPackage pyproject-nix.build.packages {
            python = pkgs.python3;
          }).overrideScope
            (
              lib.composeManyExtensions [
                pyproject-build-systems.overlays.wheel
                workspaceOverlay
                buildToolsOverlay
              ]
            );
        applicationPackage = pythonSet.mkVirtualEnv packageName runtimeDeps;
        editableSet = pythonSet.overrideScope editableOverlay;
        devVirtualenv = editableSet.mkVirtualEnv devPackageName devDeps;

        # Container image
        dockerImage = pkgs.dockerTools.buildLayeredImage {
          name = "tradefog";
          tag = imageTag;

          contents = [
            applicationPackage
            pkgs.dockerTools.binSh
            pkgs.dockerTools.caCertificates
          ];

          enableFakechroot = true;
          fakeRootCommands = ''
            ${pkgs.dockerTools.shadowSetup}

            groupadd -r -g ${toString containerUid} ${containerUser}
            useradd -r \
              -u ${toString containerUid} \
              -g ${containerUser} \
              -d ${containerRoot} \
              -s /bin/sh \
              ${containerUser}

            mkdir -p \
              ${containerRoot}/config/tradefog \
              ${containerRoot}/data/tradefog \
              ${containerRoot}/cache/tradefog \
              ${containerRoot}/state/tradefog
            chown -R ${containerUser}:${containerUser} ${containerRoot}
          '';

          config = {
            User = "${containerUser}:${containerUser}";
            WorkingDir = containerRoot;

            Labels = {
              "org.opencontainers.image.title" = "Tradefog";
              "org.opencontainers.image.description" = project.project.description;
              "org.opencontainers.image.version" = version;
              "org.opencontainers.image.revision" = revision;
              "org.opencontainers.image.source" = "https://github.com/MOIS3Y/tradefog";
              "org.opencontainers.image.authors" = "MOIS3Y <stepan@zhukovsky.me>";
              "org.opencontainers.image.licenses" = "GPL-3.0-only";
            };

            Env = [
              # Runtime directories
              "HOME=${containerRoot}"
              "XDG_CONFIG_HOME=${containerRoot}/config"
              "XDG_DATA_HOME=${containerRoot}/data"
              "XDG_CACHE_HOME=${containerRoot}/cache"
              "XDG_STATE_HOME=${containerRoot}/state"

              # Python runtime
              "PYTHONUNBUFFERED=1"
              "PYTHONDONTWRITEBYTECODE=1"
            ];

            Entrypoint = [ "/bin/tradefog" ];
            Cmd = [
              "serve"
              "--host"
              "0.0.0.0"
            ];
            StopSignal = "SIGINT";
            ExposedPorts = {
              "8000/tcp" = { };
            };
          };
        };
      in
      {
        packages = {
          default = applicationPackage;
        }
        // lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
          docker = dockerImage;
        };

        apps.default = {
          type = "app";
          program = "${applicationPackage}/bin/tradefog";
          meta.description = "Run tradefog";
        };

        devShells.default = pkgs.mkShell {
          packages = [
            devVirtualenv
            pkgs.dart-sass
            pkgs.gettext
            pkgs.git
            pkgs.uv
          ];
          env = {
            # uv
            UV_NO_SYNC = "1";
            UV_PYTHON = editableSet.python.interpreter;
            UV_PYTHON_DOWNLOADS = "never";
          };
          shellHook = ''
            tradefog_reset_environment() {
              # Python
              unset PYTHONPATH

              # Application paths
              unset TRADEFOG_DATABASE__SQLITE__PATH
              unset TRADEFOG_STATIC__ROOT
              unset TRADEFOG_MEDIA__ROOT
            }

            tradefog_set_repository_root() {
              export REPO_ROOT="$(git rev-parse --show-toplevel)"
            }

            tradefog_prepare_runtime_directories() {
              local tradefog_runtime_root="$REPO_ROOT/.runtime"

              mkdir -p \
                "$tradefog_runtime_root/config/tradefog" \
                "$tradefog_runtime_root/data/tradefog" \
                "$tradefog_runtime_root/cache/tradefog" \
                "$tradefog_runtime_root/state/tradefog"
            }

            tradefog_prepare_configuration() {
              local tradefog_runtime_root="$REPO_ROOT/.runtime"
              local tradefog_config_dir
              local tradefog_config_path

              tradefog_config_dir="$tradefog_runtime_root/config/tradefog"
              tradefog_config_path="$tradefog_config_dir/settings.toml"

              if [ ! -e "$tradefog_config_path" ]; then
                install -m 600 \
                  ${developmentSettings} \
                  "$tradefog_config_path"
              fi

              export TRADEFOG_CONFIG="$tradefog_config_path"
            }

            tradefog_compile_translations() {
              find "$REPO_ROOT/src/tradefog/locale" -name '*.po' \
                -exec sh -c '
                  for catalog do
                    msgfmt --check -o "''${catalog%.po}.mo" "$catalog"
                  done
                ' sh {} +
            }

            tradefog_build_frontend_assets() {
              python -m tradefog.assets.build
            }

            tradefog_collect_static() {
              python -m tradefog setup --collect-static
            }

            tradefog_reset_environment
            tradefog_set_repository_root
            tradefog_prepare_runtime_directories
            tradefog_prepare_configuration
            tradefog_compile_translations
            tradefog_build_frontend_assets
            tradefog_collect_static

            unset -f \
              tradefog_reset_environment \
              tradefog_set_repository_root \
              tradefog_prepare_runtime_directories \
              tradefog_prepare_configuration \
              tradefog_compile_translations \
              tradefog_build_frontend_assets \
              tradefog_collect_static
          '';
        };
      }
    );
}
