# Windows Image Patching Tool (WIPT)

WIPT (Windows Image Patching Tool) is a native Windows Command-Line Interface (CLI) tool, with an optional Graphical User Interface (GUI), designed to simplify the process of patching Android boot images (and related formats) with Magisk. It aims to provide a straightforward way for Windows users to handle common Android image modification tasks without needing WSL (Windows Subsystem for Linux) or a separate Linux environment.

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
*   **Basic Graphical User Interface (GUI):** Offers an alternative way to use WIPT for selecting files, options, and viewing logs.
*   **Customizable Output:** Allows specifying a custom output filename and provides overwrite protection for output files.
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

    **Note:** The `setup.py` script tries to fetch the latest Magisk assets from GitHub. If this fails, you might need to manually populate `vendor/magisk-assets/` (see `setup.py` for expected file names). After setup, you can launch the CLI or GUI version of WIPT.

## Usage

After running `setup.bat` successfully, you can launch WIPT.

### Launching the GUI

To use the Graphical User Interface:
1.  Ensure `setup.bat` has completed successfully.
2.  In the WIPT project directory, run:
    ```batch
    run_wipt_gui.bat
    ```
This will open the WIPT GUI window. From the GUI, you can:
*   Browse for your input image file.
*   Browse for an output directory.
*   See a suggested output filename (which you can modify if needed).
*   Select the patcher (currently Magisk).
*   Choose Magisk-specific options (target architecture, verity, forceencrypt, etc.).
*   Start the patching process.
*   View logs in real-time.

### Using the CLI

To use the Command-Line Interface:
1.  Ensure `setup.bat` has completed successfully.
2.  Open a Command Prompt or PowerShell in the WIPT project directory.
3.  Use `run_wipt.bat` to execute WIPT commands. This script automatically activates the virtual environment.

**General CLI Syntax:**
```batch
run_wipt.bat <command> [options...]
```
Currently, the primary command is `patch`.

**Patch Command (CLI):**

Patches a boot image with Magisk.

**Syntax:**
```batch
run_wipt.bat patch --input <input_file_path> --output <output_directory> [--magisk] [Options...]
```

**Required CLI Arguments:**

*   `--input <input_file_path>`: Path to the input boot image (e.g., `boot.img`, `boot.img.lz4`, `firmware.tar`).
*   `--output <output_directory>`: Path to the directory where the patched file will be saved.

**General Patch Options (CLI & GUI):**

*   `--output-filename <filename>` (CLI only for now, GUI has an entry): Specify a custom name for the output file. If not provided, a name like `<original_base>_patched.<ext>` will be used.
*   `--allow-overwrite` (CLI only for now, GUI has a checkbox): If the output file already exists, this flag allows WIPT to overwrite it. Without this flag, an error will occur if the file exists.

**Patcher Selection (CLI & GUI):**

*   `--magisk` (CLI flag): Explicitly select Magisk for patching. Usually implied if other Magisk options are used. (GUI: Radio button)

**Magisk Options (CLI & GUI):**

*   `--target_arch <arch>`: Specifies the target CPU architecture.
    *   Choices: `arm`, `arm64`, `x86`, `x64`. Default: `arm64`.
*   `--keep_verity`: Preserve AVB/dm-verity.
*   `--keep_forceencrypt`: Preserve force encryption.
*   `--patch_vbmeta_flag`: Patch VBMeta flags in boot image header.
*   `--recovery_mode`: Patch for recovery mode.
*   `--legacy_sar`: Patch for legacy System-As-Root devices.

**CLI Example:**
```batch
run_wipt.bat patch --input my_boot.img.lz4 --output PatchedFiles --magisk --target_arch arm64 --keep_verity --output-filename custom_patched_boot.img.lz4 --allow-overwrite
```

### Manual Usage (CLI or GUI without batch files)

If you prefer, you can activate the virtual environment manually:
```batch
REM In the WIPT project directory
call .venv\Scripts\activate.bat
```
Then run:
```bash
python wipt.py patch --input <input_file> --output <output_dir> ... (for CLI)
python wipt_gui.py (for GUI)
```
Remember to `deactivate` when done if you manually activated.

## How it Works (Simplified)

1.  **Preparation:** Input file type is detected. Archives are extracted, compressed files are decompressed. A plain boot image is prepared.
2.  **Patching (Magisk):** Architecture-specific Magisk assets are used with `magiskboot` to unpack the boot image, modify its ramdisk (adding `magiskinit`, Magisk binaries, etc., respecting selected options), and repack it.
3.  **Repackaging:** The patched boot image is repackaged into its original format (e.g., re-compressed if input was LZ4, rebuilt into a TAR archive if input was TAR, preserving other files). The output filename is determined by user input or defaults to `*_patched`.
4.  **Cleanup:** Temporary files and directories are removed.

## Future Development
*   Full APatch integration.
*   Support for more image types (e.g., `super.img` processing, `payload.bin` extraction).
*   Enhanced GUI features (e.g., progress bars, cancellation).
*   More robust error handling and user feedback across CLI and GUI.
*   Investigation into boot image architecture auto-detection to simplify `--target_arch` selection.

## Contributing & Issues
Contributions are welcome! Please refer to `CONTRIBUTING.md` (to be created) for guidelines.
If you encounter any bugs or have feature requests, please open an issue on the GitHub repository.

---
*This README provides a user-focused overview. For more technical details, see [README.markdown](README.markdown).*
