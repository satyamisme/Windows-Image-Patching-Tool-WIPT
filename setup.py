import os
import requests
import zipfile
import shutil
import stat # For setting executable permissions if needed

# --- Constants ---
# GitHub API URL for the latest Magisk release
MAGISK_API_URL = "https://api.github.com/repos/topjohnwu/Magisk/releases/latest"
# Directory to store downloaded and extracted assets
ASSET_DIR = os.path.join("vendor", "magisk-assets")
# Precompiled magiskboot for Windows (example source)
# Users might need to find a reliable, up-to-date source if this one is outdated or unavailable.
MAGISKBOOT_WINDOWS_URL = "https://github.com/svoboda18/magiskboot/releases/download/0320/magiskboot.exe" # Example URL

# Assets to extract from Magisk APK and their target names
# (source_path_in_apk, target_filename_in_asset_dir)
APK_ASSET_MAP = {
    "assets/magiskinit": "magiskinit",
    "assets/magisk64": "magisk64",
    "assets/magisk32": "magisk32",
    "assets/init_ld.so": "init-ld", # Example, actual name might vary or not be needed directly
    "assets/stub.apk": "stub.apk"
}

# --- Helper Functions ---
def download_file(url, destination):
    """Downloads a file from a URL to a destination, with error handling."""
    print(f"Downloading {url} to {destination}...")
    try:
        response = requests.get(url, stream=True, timeout=30) # 30-second timeout
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Ensure destination directory exists
        os.makedirs(os.path.dirname(destination), exist_ok=True)

        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download successful.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
    except IOError as e:
        print(f"Error writing to {destination}: {e}")
    return False

def extract_from_apk(apk_path, assets_map, target_dir):
    """Extracts specified files from an APK to a target directory."""
    print(f"Extracting assets from {apk_path} to {target_dir}...")
    extracted_files = []
    try:
        with zipfile.ZipFile(apk_path, 'r') as apk_zip:
            for asset_path_in_apk, target_filename in assets_map.items():
                full_target_path = os.path.join(target_dir, target_filename)
                print(f"  Attempting to extract: {asset_path_in_apk} -> {target_filename}")
                try:
                    # Extract to a temporary name first to avoid issues with zipfile's interpretation of paths
                    # ZipFile.extract will create subdirectories if path_in_apk contains them.
                    # We want to place it directly in target_dir with target_filename.

                    # Read the file data from APK
                    file_data = apk_zip.read(asset_path_in_apk)

                    # Write it to the desired target path
                    with open(full_target_path, 'wb') as f_out:
                        f_out.write(file_data)

                    print(f"    Successfully extracted {asset_path_in_apk} to {full_target_path}")
                    extracted_files.append(full_target_path)

                    # If the asset is one of the main executables (magiskinit, magisk32, magisk64)
                    # and not on Windows, set executable permissions.
                    if target_filename in ["magiskinit", "magisk32", "magisk64"] and os.name != 'nt':
                        try:
                            current_mode = os.stat(full_target_path).st_mode
                            os.chmod(full_target_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                            print(f"    Set executable permission for {target_filename}")
                        except Exception as e_perm:
                            print(f"    Warning: Could not set executable permission for {target_filename}: {e_perm}")

                except KeyError:
                    print(f"    Warning: Asset {asset_path_in_apk} not found in APK.")
                except Exception as e_extract:
                    print(f"    Error extracting {asset_path_in_apk}: {e_extract}")

        if extracted_files:
            print("Extraction process completed (some warnings may have occurred).")
        else:
            print("No assets were successfully extracted from the APK based on the map.")
        return len(extracted_files) > 0

    except zipfile.BadZipFile:
        print(f"Error: {apk_path} is not a valid zip file or is corrupted.")
    except FileNotFoundError:
        print(f"Error: APK file {apk_path} not found.")
    except Exception as e_zip_open:
        print(f"Error opening or processing APK {apk_path}: {e_zip_open}")
    return False


# --- Main Setup Logic ---
def main():
    print("WIPT Setup Script - Fetching Magisk Assets")

    # Create the main asset directory
    if not os.path.exists(ASSET_DIR):
        os.makedirs(ASSET_DIR)
        print(f"Created asset directory: {ASSET_DIR}")

    # 1. Download the latest Magisk APK
    magisk_apk_url = None
    magisk_apk_path = os.path.join(ASSET_DIR, "Magisk.apk")

    print(f"Attempting to get latest Magisk release info from {MAGISK_API_URL}...")
    try:
        response = requests.get(MAGISK_API_URL, timeout=10)
        response.raise_for_status()
        release_info = response.json()

        for asset in release_info.get("assets", []):
            if asset.get("name", "").lower().endswith(".apk"):
                magisk_apk_url = asset.get("browser_download_url")
                print(f"Found Magisk APK download URL: {magisk_apk_url}")
                break
        if not magisk_apk_url:
            print("Error: Could not find Magisk APK download URL in the latest release.")
            # Fallback or direct link if API fails often or for offline use:
            # magisk_apk_url = "MANUAL_FALLBACK_LINK_TO_MAGISK.APK"
            # print(f"Using fallback Magisk APK URL: {magisk_apk_url}")


    except requests.exceptions.RequestException as e:
        print(f"Error fetching Magisk release info: {e}")
        print("Skipping Magisk APK download due to API fetch error.")
    except Exception as e_json: # Catch other errors like JSON parsing
        print(f"Error processing Magisk release info: {e_json}")
        print("Skipping Magisk APK download.")

    if magisk_apk_url:
        if not download_file(magisk_apk_url, magisk_apk_path):
            print("Failed to download Magisk APK. Some assets might be missing.")
            magisk_apk_path = None # Ensure it's None if download failed
    else:
        magisk_apk_path = None # Ensure it's None if no URL

    # 2. Extract assets from the downloaded APK (if successful)
    if magisk_apk_path and os.path.exists(magisk_apk_path):
        if not extract_from_apk(magisk_apk_path, APK_ASSET_MAP, ASSET_DIR):
            print("Failed to extract some or all assets from Magisk APK.")
    elif magisk_apk_url: # if URL was found but download failed
        print(f"Magisk APK was not downloaded from {magisk_apk_url}, so assets cannot be extracted.")
    else:
        print("No Magisk APK URL was determined, so assets cannot be extracted.")


    # 3. Download magiskboot (OS-dependent)
    # For non-Windows, magiskboot should ideally be compiled from source or extracted from Magisk's magiskinit
    # For Windows, precompiled binaries are often used.
    magiskboot_final_path = os.path.join(ASSET_DIR, "magiskboot.exe" if os.name == 'nt' else "magiskboot")

    if os.name == 'nt':
        print("Attempting to download magiskboot.exe for Windows...")
        if not download_file(MAGISKBOOT_WINDOWS_URL, magiskboot_final_path):
            print("Failed to download magiskboot.exe for Windows.")
            print(f"Please ensure you have '{os.path.basename(magiskboot_final_path)}' in '{ASSET_DIR}'.")
        else:
            # No need to chmod on Windows typically for .exe
            pass
    else: # Linux/macOS
        # On Linux/macOS, magiskboot is part of magiskinit.
        # One common way is to have magiskinit act as magiskboot.
        # We can try to symlink or copy magiskinit to magiskboot if magiskinit was extracted.
        magiskinit_path = os.path.join(ASSET_DIR, "magiskinit")
        if os.path.exists(magiskinit_path):
            print(f"Attempting to make 'magiskinit' available as 'magiskboot' for non-Windows OS...")
            try:
                # Create a copy named magiskboot, or a symlink
                # Copying is safer for cross-filesystem or if original is changed.
                shutil.copy2(magiskinit_path, magiskboot_final_path)
                # Ensure it's executable
                current_mode = os.stat(magiskboot_final_path).st_mode
                os.chmod(magiskboot_final_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                print(f"Successfully copied 'magiskinit' to '{magiskboot_final_path}' and made it executable.")
            except Exception as e_link:
                print(f"Error making magiskinit available as magiskboot: {e_link}")
                print(f"Please ensure you have an executable 'magiskboot' in '{ASSET_DIR}'.")
        else:
            print(f"'magiskinit' not found in {ASSET_DIR}. Cannot create 'magiskboot' from it.")
            print(f"Please ensure you have an executable 'magiskboot' in '{ASSET_DIR}'.")


    # --- Summary ---
    print("\n--- WIPT Setup Summary ---")
    print(f"Magisk assets are expected in: {os.path.abspath(ASSET_DIR)}")
    critical_files = [
        magiskboot_final_path, # magiskboot or magiskboot.exe
        os.path.join(ASSET_DIR, "magiskinit"),
        os.path.join(ASSET_DIR, "magisk64"),
        os.path.join(ASSET_DIR, "magisk32")
    ]
    print("Expected critical files:")
    for f_path in critical_files:
        status = "FOUND" if os.path.exists(f_path) else "MISSING"
        print(f"  - {f_path} : {status}")

    if not os.path.exists(magiskboot_final_path):
        print("\nWARNING: magiskboot was not successfully obtained. Patching will likely fail.")
        if os.name != 'nt':
             print("On Linux/macOS, ensure 'magiskinit' was extracted and could be copied/linked to 'magiskboot'.")
        else:
             print(f"Ensure '{MAGISKBOOT_WINDOWS_URL}' is a valid link or place 'magiskboot.exe' manually.")

    print("\nSetup script finished. Please check for any errors above.")
    print("If critical files are missing, WIPT may not function correctly.")

if __name__ == "__main__":
    main()
