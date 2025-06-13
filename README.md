# Windows Image Patching Tool (WIPT)

WIPT (Windows Image Patching Tool) is a native Windows Command-Line Interface (CLI) tool designed to simplify the process of patching Android boot images (and related formats) with Magisk. It aims to provide a straightforward way for Windows users to handle common Android image modification tasks without needing WSL (Windows Subsystem for Linux) or a separate Linux environment.

For more detailed technical information, original development plans, and broader project scope, please see [README.markdown](README.markdown).

## Features (Current)

*   **Magisk Patching:** Applies Magisk to plain boot images (`.img`) and boot images packaged in:
    *   LZ4 compressed format (`.img.lz4`)
    *   TAR archives (`.tar`)
    *   LZ4 compressed TAR archives (`.tar.lz4`)
*   **Format Handling:** Automatically detects and handles the specified input formats for unpacking and repackaging.
*   **Architecture Specificity:** Allows specifying the target CPU architecture for Magisk assets (e.g., arm64, arm, x86, x64).
*   **TAR Content Preservation:** When patching a boot image within a TAR archive, WIPT attempts to preserve other files and the directory structure present in the original TAR.
*   **User-Friendly CLI:** Provides clear command-line options for specifying inputs, outputs, and patching choices.
*   **Automated Setup:** Includes a setup script (`setup.bat`) to prepare the Python environment and attempt to download necessary Magisk assets.

## Setup

### Prerequisites

1.  **Windows:** Windows 10 or 11 (64-bit recommended).
2.  **Python:** Python 3.10 or newer. Ensure Python is added to your system's PATH during installation. You can download Python from [python.org](https://www.python.org/).
3.  **Git (Optional but Recommended):** For cloning this repository. Download from [git-scm.com](https://git-scm.com/).
4.  **LZ4 (for testing):** If you plan to create or test with `.img.lz4` or `.tar.lz4` files locally, you might need the LZ4 command-line tool. This is not required for WIPT to *process* these files if they are provided as input, as the `lz4` Python library handles it.

### Installation Steps

1.  **Clone the Repository (if you haven't already):**
    ```bash
    git clone <repository_url>
    cd wipt
    ```
    (Replace `<repository_url>` with the actual URL of the WIPT repository). If you downloaded the source as a ZIP, extract it and navigate to the directory.

2.  **Run the Setup Script:**
    Open a Command Prompt (`cmd.exe`) in the WIPT project directory and run:
    ```batch
    setup.bat
    ```
    This script will:
    *   Check for Python.
    *   Create a Python virtual environment in a folder named `.venv`.
    *   Activate the virtual environment for its session.
    *   Install required Python packages from `requirements.txt`.
    *   Run `python setup.py` which attempts to download Magisk assets (like `magiskboot`, `magiskinit`, etc.) into the `vendor/magisk-assets/` directory.

    **Note:** The `setup.py` script tries to fetch the latest Magisk assets from GitHub. If this fails (e.g., due to network issues or changes in GitHub release structures), you might need to manually populate the `vendor/magisk-assets/` directory with the required files (see `setup.py` for details on expected file names like `magiskboot.exe`, `magisk_arm64`, `magiskinit_arm64`, etc.).

## Usage

After running `setup.bat` successfully, you can use `run_wipt.bat` to execute the tool. This batch script automatically activates the virtual environment.

**General Syntax:**
```batch
run_wipt.bat <command> [options...]
```

Currently, the primary command is `patch`.

### Patch Command

Patches a boot image with Magisk.

**Syntax:**
```batch
run_wipt.bat patch --input <input_file_path> --output <output_directory> [--magisk] [Magisk_Options...]
```

**Required Arguments:**

*   `--input <input_file_path>`: Path to the input boot image. This can be:
    *   A plain boot image (e.g., `boot.img`).
    *   An LZ4 compressed boot image (e.g., `boot.img.lz4`).
    *   A TAR archive containing a boot image (e.g., `firmware.tar`).
    *   An LZ4 compressed TAR archive containing a boot image (e.g., `firmware.tar.lz4`).
*   `--output <output_directory>`: Path to the directory where the patched file will be saved. The patched file will typically be named like `<original_base_name>_patched.<original_extension>`.

**Patcher Selection (Optional, defaults to Magisk if any Magisk options are given or if it's the only patcher):**

*   `--magisk`: Explicitly select Magisk for patching. This is usually implied if other Magisk options are used.

**Magisk Options (used if `--magisk` is specified or implied):**

*   `--target_arch <arch>`: Specifies the target CPU architecture for Magisk assets.
    *   Choices: `arm`, `arm64`, `x86`, `x64`.
    *   Default: `arm64`.
    *   Example: `--target_arch arm`
*   `--keep_verity`: Corresponds to Magisk's `KEEPVERITY` option (preserve AVB/dm-verity).
*   `--keep_forceencrypt`: Corresponds to Magisk's `KEEPFORCEENCRYPT` option (preserve force encryption).
*   `--patch_vbmeta_flag`: Corresponds to Magisk's `PATCHVBMETAFLAG` option (patch VBMeta flags in boot image header).
*   `--recovery_mode`: Corresponds to Magisk's `RECOVERYMODE` option (patch for recovery mode).
*   `--legacy_sar`: Corresponds to Magisk's `LEGACYSAR` option (patch for legacy System-As-Root devices).

**Example:**
```batch
run_wipt.bat patch --input my_boot_image.img.lz4 --output PatchedFiles --magisk --target_arch arm64 --keep_verity
```
This command will:
1.  Decompress `my_boot_image.img.lz4` to a plain `my_boot_image.img`.
2.  Patch `my_boot_image.img` using Magisk arm64 assets, keeping verity.
3.  Re-compress the patched image to LZ4 format.
4.  Save it as `PatchedFiles/my_boot_image_patched.img.lz4`.

### Manual Usage (without `run_wipt.bat`)

If you prefer, you can activate the virtual environment manually and then run `wipt.py`:
```batch
REM In the WIPT project directory
call .venv\Scripts\activate.bat
python wipt.py patch --input <input_file> --output <output_dir> ...
deactivate
```

## How it Works (Simplified)

1.  **Preparation (`prepare_boot_image_for_patching`):**
    *   The input file type is detected.
    *   If it's an archive (.tar, .tar.lz4), the boot image is extracted. The name of the boot image file within the archive is noted.
    *   If it's compressed (.img.lz4), it's decompressed.
    *   A plain boot image is placed in a temporary working directory.
2.  **Patching (`MagiskPatcher.patch_boot_image`):**
    *   Architecture-specific Magisk assets (e.g., `magisk_arm64`, `magiskinit_arm64`) are identified based on the `--target_arch` option.
    *   These assets, along with `stub.apk` (if found), are prepared and compressed (usually to `.xz`).
    *   The `magiskboot` executable is used to:
        *   `unpack` the plain boot image.
        *   Modify the ramdisk (`ramdisk.cpio`) by adding `magiskinit` (as `init`), the compressed Magisk binaries, and the stub. This step respects options like `KEEPVERITY`.
        *   `repack` the boot image with the modified ramdisk. This produces a `new-boot.img` (or similar) in the temporary directory.
3.  **Repackaging (`repackage_patched_boot_image`):**
    *   The patched `new-boot.img` is taken from the temporary directory.
    *   If the original input was a TAR archive, a new TAR archive is constructed:
        *   Other files and directories from the original TAR are carried over.
        *   The original boot image within the TAR is replaced with the patched version, preserving its original filename within the archive.
    *   If the original input (or the TAR archive) was LZ4 compressed, the result is re-compressed to LZ4.
    *   The final patched file is saved to the specified output directory.
4.  **Cleanup:** The temporary working directory and its contents are removed.

## Future Development
*   APatch integration.
*   Support for more image types (e.g., `super.img`, `payload.bin` extraction).
*   GUI wrapper (potential).
*   More robust error handling and user feedback.

## Contributing & Issues
Contributions are welcome! Please refer to `CONTRIBUTING.md` (to be created) for guidelines.
If you encounter any bugs or have feature requests, please open an issue on the GitHub repository.

---
*This README provides a user-focused overview. For more technical details, see [README.markdown](README.markdown).*
