# WIPT Testing Guidelines

This document outlines test cases for the Windows Image Patching Tool (WIPT), focusing on the `patch` command's ability to handle various input formats for boot images.

**General Prerequisites for Testing:**
*   `wipt.py` is executable and in the PATH or called as `python wipt.py`.
*   Python environment with all dependencies from `requirements.txt` installed.
*   A placeholder `magiskboot` executable (even if non-functional, just to pass initial path checks in `MagiskPatcher`) should be placed at `vendor/magisk-assets/magiskboot` (or `magiskboot.exe` on Windows). For these tests, the actual patching logic of `magiskboot` is not the primary focus, but rather the file handling and pipeline of `wipt.py`.
*   An output directory (e.g., `test_output/`) should be created or will be created by the script.

---

## Test Case 1: Plain `boot.img`

*   **Input:**
    *   A dummy plain boot image file named `dummy_boot.img`.
    *   Content: "This is a dummy plain boot.img."
    *   Create command: `echo "This is a dummy plain boot.img." > dummy_boot.img`

*   **Command:**
    ```bash
    python wipt.py patch --input dummy_boot.img --output test_output --magisk --keep_verity
    ```

*   **Expected `wipt.py` Behavior:**
    1.  **Format Detection:** `get_file_type("dummy_boot.img")` should return `"boot.img"`.
    2.  **Preparation:** `prepare_boot_image_for_patching` will:
        *   Create a temporary directory (e.g., `/tmp/xxxx_wipt_patch/`).
        *   Copy `dummy_boot.img` into this temporary directory.
        *   Return the path to this copied `dummy_boot.img` in the temp dir, original type `"boot.img"`, and the temp dir path.
    3.  **MagiskPatcher Invocation:**
        *   `MagiskPatcher` instance is created.
        *   `patcher_options` will include `KEEPVERITY=True`.
        *   `patch_boot_image` method is called with the path to `dummy_boot.img` in the temp dir.
        *   `_exec_magiskboot` will be called (and is expected to fail if `magiskboot` is a placeholder or not found, or succeed if a functional one is present).
        *   Assume for this test flow that a (mocked/placeholder) patched image is produced in the temp dir (e.g., `new-boot.img` or `magisk_patched_64.img`).
    4.  **Repackaging:** `repackage_patched_boot_image` will:
        *   Take the (mocked) patched image from the temp dir.
        *   Since the original type was `"boot.img"`, it will copy this to `test_output/dummy_boot_patched.img`.
    5.  **Cleanup:** The temporary directory is removed.

*   **Verification:**
    *   **Logs:**
        *   Confirm detection as `"boot.img"`.
        *   Confirm copy to temp directory.
        *   Confirm `MagiskPatcher` options show `KEEPVERITY=True`.
        *   (If `magiskboot` is a placeholder) Confirm logs indicating `magiskboot` execution attempt and subsequent (expected) failure/error message if it's not functional.
        *   Confirm repackaging message for `"boot.img"`.
        *   Confirm temporary directory cleanup message.
    *   **Output File:**
        *   `test_output/dummy_boot_patched.img` should exist.
        *   Its content should match the (mocked) patched boot image content.
    *   **Temp Directory:** Ensure the temporary directory is no longer present.

---

## Test Case 2: LZ4 Compressed `boot.img` (`.img.lz4`)

*   **Input:**
    *   A dummy plain boot image file named `dummy_boot_for_lz4.img`.
    *   Content: "This is a dummy boot image for LZ4 compression."
    *   Create command: `echo "This is a dummy boot image for LZ4 compression." > dummy_boot_for_lz4.img`
    *   Compress it: `lz4 dummy_boot_for_lz4.img dummy_boot.img.lz4` (Requires `lz4` CLI tool or Python LZ4 to prepare test file).

*   **Command:**
    ```bash
    python wipt.py patch --input dummy_boot.img.lz4 --output test_output --magisk --target_arch arm
    ```

*   **Expected `wipt.py` Behavior:**
    1.  **Format Detection:** `get_file_type("dummy_boot.img.lz4")` should return `"boot.img.lz4"`.
    2.  **Preparation:** `prepare_boot_image_for_patching` will:
        *   Create a temporary directory.
        *   Decompress `dummy_boot.img.lz4` into this temporary directory as `dummy_boot.img`.
        *   Return the path to this decompressed `dummy_boot.img`, original type `"boot.img.lz4"`, and the temp dir path.
    3.  **MagiskPatcher Invocation:**
        *   `MagiskPatcher` instance is created.
        *   `patcher_options` will include `TARGET_ARCH_SUFFIX="32"`.
        *   `patch_boot_image` is called with the path to the decompressed `dummy_boot.img`.
        *   (Placeholder `magiskboot` execution).
        *   Assume a (mocked) patched image is produced in the temp dir.
    4.  **Repackaging:** `repackage_patched_boot_image` will:
        *   Take the (mocked) patched image.
        *   Since original type was `"boot.img.lz4"`, it will re-compress this image as LZ4 into `test_output/dummy_boot_patched.img.lz4`.
    5.  **Cleanup:** The temporary directory is removed.

*   **Verification:**
    *   **Logs:**
        *   Confirm detection as `"boot.img.lz4"`.
        *   Confirm decompression messages.
        *   Confirm `MagiskPatcher` options show `TARGET_ARCH_SUFFIX="32"`.
        *   (Placeholder `magiskboot` logs).
        *   Confirm repackaging message for `"boot.img.lz4"` (re-compression).
        *   Confirm temporary directory cleanup.
    *   **Output File:**
        *   `test_output/dummy_boot_patched.img.lz4` should exist.
        *   It should be a valid LZ4 compressed file.
        *   When decompressed, its content should match the (mocked) patched boot image.
    *   **Temp Directory:** Ensure cleanup.

---

## Test Case 3: TAR Archived `boot.img` (`.tar`)

*   **Input:**
    *   A dummy plain boot image file named `my_boot.img` (note different name for testing tar extraction).
    *   Content: "This is a boot.img within a tar."
    *   Create command: `echo "This is a boot.img within a tar." > my_boot.img`
    *   Archive it: `tar -cf dummy_boot.tar my_boot.img` (Ensure `my_boot.img` is at the root of the tar).

*   **Command:**
    ```bash
    python wipt.py patch --input dummy_boot.tar --output test_output --magisk
    ```

*   **Expected `wipt.py` Behavior:**
    1.  **Format Detection:** `get_file_type("dummy_boot.tar")` should return `"boot.tar"`.
    2.  **Preparation:** `prepare_boot_image_for_patching` will:
        *   Create a temporary directory.
        *   Extract `my_boot.img` from `dummy_boot.tar` into the temporary directory.
        *   Return path to this extracted `my_boot.img`, original type `"boot.tar"`, and temp dir path.
    3.  **MagiskPatcher Invocation:**
        *   Called with the path to extracted `my_boot.img`.
        *   (Placeholder `magiskboot` execution).
        *   Assume a (mocked) patched `my_boot.img` is produced.
    4.  **Repackaging:** `repackage_patched_boot_image` will:
        *   Take the (mocked) patched `my_boot.img`.
        *   Since original type was `"boot.tar"`, it will create a new TAR archive `test_output/dummy_boot_patched.tar` containing this patched `my_boot.img`.
    5.  **Cleanup:** The temporary directory is removed.

*   **Verification:**
    *   **Logs:**
        *   Confirm detection as `"boot.tar"`.
        *   Confirm extraction of `my_boot.img` from tar.
        *   (Placeholder `magiskboot` logs).
        *   Confirm repackaging message for `"boot.tar"` (re-archiving).
        *   Confirm temporary directory cleanup.
    *   **Output File:**
        *   `test_output/dummy_boot_patched.tar` should exist.
        *   It should be a valid TAR archive.
        *   When extracted, it should contain a file (e.g., `my_boot.img`) whose content matches the (mocked) patched boot image.
    *   **Temp Directory:** Ensure cleanup.

---

## Test Case 4: TAR.LZ4 Archived `boot.img` (`.tar.lz4`)

*   **Input:**
    *   A dummy plain boot image file named `actual_boot.img`.
    *   Content: "This is boot.img within tar.lz4."
    *   Create command: `echo "This is boot.img within tar.lz4." > actual_boot.img`
    *   Archive it: `tar -cf temp_boot.tar actual_boot.img`
    *   Compress it: `lz4 temp_boot.tar dummy_boot.tar.lz4` (Requires `lz4` CLI or Python LZ4).
    *   Clean up: `rm temp_boot.tar actual_boot.img`

*   **Command:**
    ```bash
    python wipt.py patch --input dummy_boot.tar.lz4 --output test_output --magisk --keep_forceencrypt
    ```

*   **Expected `wipt.py` Behavior:**
    1.  **Format Detection:** `get_file_type("dummy_boot.tar.lz4")` should return `"boot.tar.lz4"`.
    2.  **Preparation:** `prepare_boot_image_for_patching` will:
        *   Create a temporary directory.
        *   Decompress `dummy_boot.tar.lz4` to `dummy_boot.tar` within the temp dir.
        *   Extract `actual_boot.img` from this temporary `dummy_boot.tar` into the temp dir.
        *   Return path to extracted `actual_boot.img`, original type `"boot.tar.lz4"`, and temp dir path.
    3.  **MagiskPatcher Invocation:**
        *   `patcher_options` will include `KEEPFORCEENCRYPT=True`.
        *   Called with path to extracted `actual_boot.img`.
        *   (Placeholder `magiskboot` execution).
        *   Assume a (mocked) patched `actual_boot.img` is produced.
    4.  **Repackaging:** `repackage_patched_boot_image` will:
        *   Take the (mocked) patched `actual_boot.img`.
        *   Create a new temporary TAR archive containing this patched image.
        *   Compress this temporary TAR archive using LZ4 to `test_output/dummy_boot_patched.tar.lz4`.
    5.  **Cleanup:** The temporary directory (including the intermediate `.tar` file) is removed.

*   **Verification:**
    *   **Logs:**
        *   Confirm detection as `"boot.tar.lz4"`.
        *   Confirm decompression of `.tar.lz4` to `.tar`.
        *   Confirm extraction of `actual_boot.img` from `.tar`.
        *   Confirm `MagiskPatcher` options show `KEEPFORCEENCRYPT=True`.
        *   (Placeholder `magiskboot` logs).
        *   Confirm repackaging messages (tarring, then lz4 compressing).
        *   Confirm temporary directory cleanup.
    *   **Output File:**
        *   `test_output/dummy_boot_patched.tar.lz4` should exist.
        *   It should be a valid LZ4 compressed TAR archive.
        *   When fully extracted (decompress lz4, then untar), it should contain `actual_boot.img` (or similar name) whose content matches the (mocked) patched boot image.
    *   **Temp Directory:** Ensure cleanup.

---
**Note on Mocking `magiskboot`:** For tests focused purely on `wipt.py`'s file handling pipeline, `magiskboot` can be a simple script that, for example, copies its input to the expected output name (e.g., `boot.img` to `new-boot.img`) and exits successfully. This would allow the rest of the `wipt.py` logic to proceed as if patching occurred.
