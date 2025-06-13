import os
import requests
import zipfile
import shutil
import stat # For setting executable permissions if needed

# --- Constants ---
MAGISK_API_URL = "https://api.github.com/repos/topjohnwu/Magisk/releases/latest"
ASSET_DIR = os.path.join("vendor", "magisk-assets")
MAGISKBOOT_WINDOWS_URL = "https://github.com/svoboda18/magiskboot/releases/download/0320/magiskboot.exe" # Example

# Architecture mapping: short_name -> path_in_apk_lib_dir
TARGET_ARCHITECTURES = {
    "arm64": "arm64-v8a",
    "arm": "armeabi-v7a",
    "x64": "x86_64", # Magisk usually uses x86_64 for its 64-bit x86 binaries
    "x86": "x86",
}

# Arch-specific assets to extract from APK's lib/<arch_path>/
# original_filename_in_apk_lib_dir -> output_filename_pattern (suffix, _{arch} will be appended)
# Note: Magisk's internal naming can change. These are common patterns.
# Example: lib/arm64-v8a/libmagiskinit.so -> magiskinit_arm64
ARCH_SPECIFIC_ASSETS_FROM_APK = {
    "libmagiskinit.so": "magiskinit", # Output: magiskinit_arm64, magiskinit_arm etc.
    "libmagisk.so": "magisk",         # Output: magisk_arm64, magisk_arm etc. (core Magisk binary)
    "libinitld.so": "initld",         # Output: initld_arm64, initld_arm etc. (linker)
    # magiskboot is often a symlink to magiskinit or part of it, or a separate binary in assets/
    # We handle magiskboot separately: either download prebuilt for Windows, or use magiskinit for others.
}

# Common assets from APK (usually from assets/ directory in APK)
# source_path_in_apk -> target_filename_in_asset_dir
COMMON_ASSETS_FROM_APK = {
    "assets/stub.apk": "stub.apk",
    "assets/util_functions.sh": "util_functions.sh", # If present and needed
    "assets/boot_patch.sh": "boot_patch.sh",       # If present and needed
    # Magiskboot might also be here for some architectures in older versions or specific builds
    # "assets/magiskboot": "magiskboot_from_assets" # Example if needed
}


# --- Helper Functions ---
def download_file(url, destination):
    print(f"Downloading {url} to {destination}...")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
        print("Download successful.")
        return True
    except requests.exceptions.RequestException as e: print(f"Error downloading {url}: {e}")
    except IOError as e: print(f"Error writing to {destination}: {e}")
    return False

def extract_assets_from_apk_refined(apk_path, target_dir):
    print(f"Extracting assets from {apk_path} to {target_dir}...")
    extracted_count = 0
    try:
        with zipfile.ZipFile(apk_path, 'r') as apk_zip:
            # 1. Extract architecture-specific assets
            for short_arch_name, apk_lib_path_segment in TARGET_ARCHITECTURES.items():
                for asset_orig_name, asset_target_pattern in ARCH_SPECIFIC_ASSETS_FROM_APK.items():
                    source_path_in_apk = f"lib/{apk_lib_path_segment}/{asset_orig_name}"
                    target_filename = f"{asset_target_pattern}_{short_arch_name}" # e.g., magiskinit_arm64
                    full_target_path = os.path.join(target_dir, target_filename)

                    print(f"  Attempting: {source_path_in_apk} -> {target_filename}")
                    try:
                        file_data = apk_zip.read(source_path_in_apk)
                        with open(full_target_path, 'wb') as f_out: f_out.write(file_data)
                        print(f"    Successfully extracted to {full_target_path}")
                        extracted_count += 1
                        # Set executable permissions if not on Windows
                        if os.name != 'nt':
                            try:
                                current_mode = os.stat(full_target_path).st_mode
                                os.chmod(full_target_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                                print(f"    Set executable permission for {target_filename}")
                            except Exception as e_perm: print(f"    Warning: Could not set executable for {target_filename}: {e_perm}")
                    except KeyError: print(f"    Info: Asset {source_path_in_apk} not found in APK (normal for some arch/asset combos).")
                    except Exception as e_extract: print(f"    Error extracting {source_path_in_apk}: {e_extract}")

            # 2. Extract common assets
            for source_path_in_apk, target_filename in COMMON_ASSETS_FROM_APK.items():
                full_target_path = os.path.join(target_dir, target_filename)
                print(f"  Attempting common asset: {source_path_in_apk} -> {target_filename}")
                try:
                    file_data = apk_zip.read(source_path_in_apk)
                    with open(full_target_path, 'wb') as f_out: f_out.write(file_data)
                    print(f"    Successfully extracted to {full_target_path}")
                    extracted_count += 1
                except KeyError: print(f"    Warning: Common asset {source_path_in_apk} not found in APK.")
                except Exception as e_extract: print(f"    Error extracting common asset {source_path_in_apk}: {e_extract}")

        if extracted_count > 0: print("Extraction process completed.")
        else: print("No assets were successfully extracted from the APK based on the defined maps.")
        return extracted_count > 0

    except zipfile.BadZipFile: print(f"Error: {apk_path} is not a valid zip file.")
    except FileNotFoundError: print(f"Error: APK file {apk_path} not found.")
    except Exception as e_zip_open: print(f"Error opening/processing APK {apk_path}: {e_zip_open}")
    return False

# --- Main Setup Logic ---
def main():
    print("WIPT Setup Script - Fetching Magisk Assets (Refined)")
    os.makedirs(ASSET_DIR, exist_ok=True)
    print(f"Asset directory: {os.path.abspath(ASSET_DIR)}")

    # 1. Download Magisk APK
    magisk_apk_url, magisk_apk_path = None, os.path.join(ASSET_DIR, "Magisk.apk")
    print(f"Getting Magisk release info from {MAGISK_API_URL}...")
    try:
        response = requests.get(MAGISK_API_URL, timeout=10)
        response.raise_for_status()
        assets = response.json().get("assets", [])
        magisk_apk_url = next((a.get("browser_download_url") for a in assets if a.get("name","").lower().endswith(".apk")), None)
        if magisk_apk_url: print(f"Found Magisk APK URL: {magisk_apk_url}")
        else: print("Error: Could not find Magisk APK URL in release.")
    except Exception as e: print(f"Error fetching/processing Magisk release info: {e}")

    if magisk_apk_url:
        if not download_file(magisk_apk_url, magisk_apk_path): magisk_apk_path = None
    else: magisk_apk_path = None

    # 2. Extract assets
    if magisk_apk_path and os.path.exists(magisk_apk_path):
        if not extract_assets_from_apk_refined(magisk_apk_path, ASSET_DIR):
            print("Failed to extract some/all assets from Magisk APK.")
    else: print("Magisk APK not downloaded or not found, skipping extraction.")

    # 3. Handle magiskboot
    magiskboot_final_path = os.path.join(ASSET_DIR, "magiskboot.exe" if os.name == 'nt' else "magiskboot")
    if os.name == 'nt':
        print("Downloading magiskboot.exe for Windows...")
        if not download_file(MAGISKBOOT_WINDOWS_URL, magiskboot_final_path):
            print(f"Failed to download magiskboot.exe. Place it manually in '{ASSET_DIR}'.")
    else: # Linux/macOS: Try to use an extracted magiskinit (e.g., magiskinit_arm64) as magiskboot
        # Find the most suitable magiskinit (prefer arm64, then arm, then others)
        preferred_magiskinit_name = None
        for arch_short_name in ["arm64", "arm", "x64", "x86"]: # Order of preference
            potential_name = f"magiskinit_{arch_short_name}"
            if os.path.exists(os.path.join(ASSET_DIR, potential_name)):
                preferred_magiskinit_name = potential_name
                break

        if preferred_magiskinit_name:
            source_magiskinit_path = os.path.join(ASSET_DIR, preferred_magiskinit_name)
            print(f"Attempting to use '{preferred_magiskinit_name}' as 'magiskboot' for non-Windows OS...")
            try:
                shutil.copy2(source_magiskinit_path, magiskboot_final_path)
                current_mode = os.stat(magiskboot_final_path).st_mode
                os.chmod(magiskboot_final_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                print(f"Successfully copied '{preferred_magiskinit_name}' to '{magiskboot_final_path}' and made executable.")
            except Exception as e: print(f"Error setting up magiskboot from {preferred_magiskinit_name}: {e}")
        else:
            print(f"No suitable magiskinit found in {ASSET_DIR} to use as magiskboot. Please provide 'magiskboot' manually.")

    # --- Summary ---
    print("\n--- WIPT Setup Summary (Refined) ---")
    print(f"Magisk assets expected in: {os.path.abspath(ASSET_DIR)}")

    # List expected arch-specific files based on successful extraction patterns
    expected_files = [magiskboot_final_path]
    for short_arch in TARGET_ARCHITECTURES.keys():
        for name_pattern in ARCH_SPECIFIC_ASSETS_FROM_APK.values():
            expected_files.append(os.path.join(ASSET_DIR, f"{name_pattern}_{short_arch}"))
    for common_target in COMMON_ASSETS_FROM_APK.values():
        expected_files.append(os.path.join(ASSET_DIR, common_target))

    # Remove duplicates and sort for cleaner print
    expected_files = sorted(list(set(expected_files)))

    print("Expected files (some are optional or arch-dependent):")
    all_critical_found = True
    for f_path in expected_files:
        status = "FOUND" if os.path.exists(f_path) else "MISSING"
        print(f"  - {os.path.basename(f_path)} : {status} (Path: {f_path})")
        if "magiskboot" in os.path.basename(f_path) and status == "MISSING": # magiskboot is critical
            all_critical_found = False
        # Consider other files critical if needed, e.g. specific arch magiskinit
        if f"magiskinit_{TARGET_ARCHITECTURES.get('arm64', 'arm64-v8a')}" in f_path and status == "MISSING":
             pass # Not strictly critical for all setups, but good to note

    if not all_critical_found or not os.path.exists(magiskboot_final_path):
         print("\nWARNING: Core 'magiskboot' or other critical assets might be missing. Patching may fail.")

    print("\nSetup script finished. Check logs for errors.")

if __name__ == "__main__":
    main()
