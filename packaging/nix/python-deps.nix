# Python deps that nixpkgs doesn't ship (pyrogram/tgcrypto were removed
# upstream; py-tgcalls/ntgcalls were never packaged) — built from PyPI.
{
  lib,
  stdenv,
  fetchurl,
  python3,
  autoPatchelfHook,
  zlib,
}:

let
  py = python3.pkgs;
  # PyPI's stable path layout: packages/<python tag>/<initial>/<name>/<file>
  wheel =
    {
      pname,
      file,
      tag ? "py3",
      sha256,
    }:
    fetchurl {
      url = "https://files.pythonhosted.org/packages/${tag}/${lib.substring 0 1 pname}/${pname}/${file}";
      inherit sha256;
    };

  ntgcallsWheels = {
    x86_64-linux = {
      file = "ntgcalls-3.0.0-cp313-cp313-manylinux_2_28_x86_64.whl";
      sha256 = "7bebbd565b869c916a7a19b9f7af0a2b5052243e6232d7092383918a074c1a10";
    };
    aarch64-linux = {
      file = "ntgcalls-3.0.0-cp313-cp313-manylinux_2_28_aarch64.whl";
      sha256 = "55ad90dccdd02a33bb73907f9e811f83293f881f03f680ad20548952f8ba50c3";
    };
  };
in
rec {
  # Native WebRTC/tgcalls library: prebuilt manylinux wheel, patched for Nix.
  ntgcalls = py.buildPythonPackage {
    pname = "ntgcalls";
    version = "3.0.0";
    format = "wheel";
    src = wheel (
      {
        pname = "ntgcalls";
        tag = "cp313";
      }
      // ntgcallsWheels.${stdenv.hostPlatform.system}
    );
    nativeBuildInputs = [ autoPatchelfHook ];
    buildInputs = [
      stdenv.cc.cc.lib
      zlib
    ];
    doCheck = false;
  };

  py-tgcalls = py.buildPythonPackage {
    pname = "py-tgcalls";
    version = "3.0.0";
    format = "wheel";
    src = wheel {
      pname = "py-tgcalls";
      file = "py_tgcalls-3.0.0-py3-none-any.whl";
      sha256 = "c736066f3f79804f6f128231f4adad228e6aefb3418a473e0a52175c0a8baf49";
    };
    dependencies = [
      py.aiohttp
      py.deprecation
      ntgcalls
    ];
    doCheck = false;
  };

  tgcrypto = py.buildPythonPackage {
    pname = "tgcrypto";
    version = "1.2.5";
    pyproject = true;
    build-system = [ py.setuptools ];
    src = fetchurl {
      url = "mirror://pypi/t/tgcrypto/TgCrypto-1.2.5.tar.gz";
      sha256 = "9bc2cac6fb9a12ef5b08f3dd500174fe374d89b660cce981f57e3138559cb682";
    };
    doCheck = false;
  };

  # Pyrogram fork; installs the `pyrogram` module.
  kurigram = py.buildPythonPackage {
    pname = "kurigram";
    version = "2.2.26";
    format = "wheel";
    src = wheel {
      pname = "kurigram";
      file = "kurigram-2.2.26-py3-none-any.whl";
      sha256 = "f53cee6119a579b74620f45b5f83d543cd3bd510a8a6a1b4b3852e21603241e9";
    };
    dependencies = [
      py.pyaes
      py.python-socks
      tgcrypto
    ];
    doCheck = false;
  };

  # The repo pins 1.4.9 (newer releases changed the API the bot relies on).
  youtube-search-python = py.buildPythonPackage {
    pname = "youtube-search-python";
    version = "1.4.9";
    format = "wheel";
    src = wheel {
      pname = "youtube-search-python";
      file = "youtube_search_python-1.4.9-py3-none-any.whl";
      sha256 = "3aca4b29c5136b12c2657a6e3e10d55f8f84ff78dc30214bd7ba27b3c5f32e47";
    };
    dependencies = [ py.httpx ];
    doCheck = false;
  };
}
