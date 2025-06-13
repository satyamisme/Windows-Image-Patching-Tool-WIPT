import argparse
import os
import tarfile
import lz4.frame
import shutil
import tempfile
import subprocess
import hashlib

# --- File Type Detection ---
def get_file_type(filepath):
    filename = os.path.basename(filepath)
    if filename.endswith(".tar.lz4"): return "boot.tar.lz4"
    if filename.endswith(".tar"): return "boot.tar"
    if filename.endswith(".img.lz4") or filepath.endswith(".lz4"):
        try:
            with open(filepath, 'rb') as f:
                if f.read(4) == b'\x04\x22\x4D\x18': # LZ4 Magic
                    return "boot.img.lz4" if filename.endswith(".img.lz4") else "lz4_generic"
        except IOError: pass
        return "boot.img.lz4" if filename.endswith(".img.lz4") else "lz4_generic"
    if filename.endswith(".img"): return "boot.img"
    return "unknown"

# --- Boot Image Preparation ---
def prepare_boot_image_for_patching(image_path):
    file_type = get_file_type(image_path)
    original_input_name = os.path.basename(image_path)
    temp_dir = tempfile.mkdtemp(suffix="_wipt_patch")
    plain_boot_img_path = None
    original_boot_img_arcname = None # For TARs, the name of the boot image member

    if file_type == "boot.img":
        shutil.copy(image_path, os.path.join(temp_dir, original_input_name))
        plain_boot_img_path = os.path.join(temp_dir, original_input_name)
        print(f"Image is already boot.img: {plain_boot_img_path}")
    elif file_type == "boot.img.lz4":
        decompressed_name = original_input_name[:-4]
        decompressed_path = os.path.join(temp_dir, decompressed_name)
        print(f"Decompressing {original_input_name} to {decompressed_path}...")
        try:
            with lz4.frame.open(image_path, 'rb') as lz4_file, open(decompressed_path, 'wb') as boot_img_file:
                shutil.copyfileobj(lz4_file, boot_img_file)
            plain_boot_img_path = decompressed_path
            print("Decompression successful.")
        except Exception as e: shutil.rmtree(temp_dir); raise Exception(f"Failed to decompress {image_path}: {e}")
    elif file_type == "boot.tar":
        print(f"Extracting boot image from {original_input_name}...")
        try:
            with tarfile.open(image_path, 'r') as tar:
                # Prioritize common boot image names
                preferred_names = ["boot.img", "recovery.img", "init_boot.img"]
                boot_member_info = None
                for member in tar.getmembers():
                    if member.name in preferred_names and member.isfile():
                        boot_member_info = member
                        break
                if not boot_member_info: # Fallback to first .img file
                    for member in tar.getmembers():
                        if member.name.endswith(".img") and member.isfile():
                            boot_member_info = member
                            print(f"Warning: Using generic .img file from tar: {member.name}")
                            break

                if boot_member_info:
                    original_boot_img_arcname = boot_member_info.name
                    # Extract to a specific name in temp_dir to avoid clashes if original name is just 'boot.img'
                    # and other operations also use 'boot.img'. Let's use its original name.
                    tar.extract(boot_member_info, path=temp_dir)
                    plain_boot_img_path = os.path.join(temp_dir, original_boot_img_arcname)
                    print(f"Extracted '{original_boot_img_arcname}' to {plain_boot_img_path}")
                else: raise Exception("Suitable boot image not found in tar archive.")
        except Exception as e: shutil.rmtree(temp_dir); raise Exception(f"Failed to extract from {image_path}: {e}")
    elif file_type == "boot.tar.lz4":
        decompressed_tar_name = original_input_name[:-4] # e.g., boot.tar
        decompressed_tar_path = os.path.join(temp_dir, decompressed_tar_name)
        print(f"Decompressing {original_input_name} to {decompressed_tar_path}...")
        try:
            with lz4.frame.open(image_path, 'rb') as lz4_file, open(decompressed_tar_path, 'wb') as tar_file:
                shutil.copyfileobj(lz4_file, tar_file)
            print("Decompression to .tar successful.")
            print(f"Extracting boot image from {decompressed_tar_path}...")
            with tarfile.open(decompressed_tar_path, 'r') as tar:
                preferred_names = ["boot.img", "recovery.img", "init_boot.img"]
                boot_member_info = None
                for member in tar.getmembers():
                    if member.name in preferred_names and member.isfile():
                        boot_member_info = member; break
                if not boot_member_info:
                    for member in tar.getmembers():
                        if member.name.endswith(".img") and member.isfile():
                            boot_member_info = member; print(f"Warning: Using generic .img from tar: {member.name}"); break

                if boot_member_info:
                    original_boot_img_arcname = boot_member_info.name
                    tar.extract(boot_member_info, path=temp_dir)
                    plain_boot_img_path = os.path.join(temp_dir, original_boot_img_arcname)
                    print(f"Extracted '{original_boot_img_arcname}' to {plain_boot_img_path}")
                else: raise Exception("Suitable boot image not found in decompressed tar archive.")
        except Exception as e: shutil.rmtree(temp_dir); raise Exception(f"Failed to process {image_path}: {e}")
    else: shutil.rmtree(temp_dir); raise ValueError(f"Unsupported file type for patching: {file_type} ({image_path})")

    if not plain_boot_img_path or not os.path.exists(plain_boot_img_path):
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        raise Exception(f"Failed to prepare plain boot image from {image_path}")

    return plain_boot_img_path, file_type, temp_dir, original_boot_img_arcname

# --- Boot Image Repackaging ---
def repackage_patched_boot_image(patched_boot_img_path, original_input_path, original_type, output_dir, original_boot_img_arcname=None):
    if not os.path.exists(patched_boot_img_path): raise FileNotFoundError(f"Patched boot img not found: {patched_boot_img_path}")
    original_basename = os.path.basename(original_input_path)
    name_parts = os.path.splitext(original_basename)
    base_name_without_double_ext = os.path.splitext(name_parts[0])[0] if name_parts[0].endswith((".tar", ".img")) else name_parts[0]
    patched_filename_base = base_name_without_double_ext + "_patched"
    os.makedirs(output_dir, exist_ok=True)
    final_output_path = None

    if original_type == "boot.img":
        final_output_path = os.path.join(output_dir, patched_filename_base + ".img")
        shutil.copy(patched_boot_img_path, final_output_path)
    elif original_type == "boot.img.lz4":
        final_output_path = os.path.join(output_dir, patched_filename_base + ".img.lz4")
        try:
            with open(patched_boot_img_path, 'rb') as f_in, lz4.frame.open(final_output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        except Exception as e: raise Exception(f"Failed to LZF compress {final_output_path}: {e}")
    elif original_type == "boot.tar":
        final_output_path = os.path.join(output_dir, patched_filename_base + ".tar")
        print(f"Rebuilding TAR archive at {final_output_path}, replacing '{original_boot_img_arcname}'...")
        try:
            with tarfile.open(original_input_path, 'r') as orig_tar, tarfile.open(final_output_path, 'w') as new_tar:
                for member in orig_tar.getmembers():
                    if original_boot_img_arcname and member.name == original_boot_img_arcname:
                        new_tar.add(patched_boot_img_path, arcname=original_boot_img_arcname)
                        print(f"  Added patched boot image as '{original_boot_img_arcname}'")
                    else:
                        if member.isfile():
                            extracted_file = orig_tar.extractfile(member)
                            new_tar.addfile(member, fileobj=extracted_file)
                        elif member.isdir() or member.issym() or member.islnk(): # Handle dirs and links
                             # For regular addfile, it expects a fileobj. For dirs/links, it might not always work as expected
                             # if it's trying to read content. A safer way for dirs/links if they are simple is to just
                             # add the member info. However, tar.add(member_path_on_disk, arcname=member.name) is more robust
                             # if we extracted the whole tar first. Given we only extract one file, this is tricky.
                             # For now, let's try adding the member directly. This might have limitations.
                             # A full extract & rebuild would be more robust for complex tars.
                            new_tar.addfile(member) # This might be problematic for some link types or empty dirs
                        else: # Other types like block/char devices, FIFOs - typically not in boot tars.
                            print(f"  Skipping non-file/dir/symlink member: {member.name} (type: {member.type})")
                print("TAR archive rebuild successful.")
        except Exception as e: raise Exception(f"Failed to rebuild tar {final_output_path}: {e}")

    elif original_type == "boot.tar.lz4":
        temp_dir_for_tarlz4 = os.path.dirname(patched_boot_img_path) # Use the same temp dir
        temp_original_tar_path = os.path.join(temp_dir_for_tarlz4, base_name_without_double_ext + "_orig_temp.tar")
        temp_new_patched_tar_path = os.path.join(temp_dir_for_tarlz4, patched_filename_base + "_temp.tar")
        final_output_path = os.path.join(output_dir, patched_filename_base + ".tar.lz4")

        print(f"Decompressing original {original_input_path} to {temp_original_tar_path} for rebuild...")
        try:
            with lz4.frame.open(original_input_path, 'rb') as lz4_in, open(temp_original_tar_path, 'wb') as tar_out:
                shutil.copyfileobj(lz4_in, tar_out)

            print(f"Rebuilding TAR to {temp_new_patched_tar_path}, replacing '{original_boot_img_arcname}'...")
            with tarfile.open(temp_original_tar_path, 'r') as orig_tar, \
                 tarfile.open(temp_new_patched_tar_path, 'w') as new_tar:
                for member in orig_tar.getmembers():
                    if original_boot_img_arcname and member.name == original_boot_img_arcname:
                        new_tar.add(patched_boot_img_path, arcname=original_boot_img_arcname)
                    else:
                        if member.isfile():
                            new_tar.addfile(member, fileobj=orig_tar.extractfile(member))
                        else: # Dirs, links
                            new_tar.addfile(member)

            print(f"Compressing {temp_new_patched_tar_path} to {final_output_path}...")
            with open(temp_new_patched_tar_path, 'rb') as tar_in, lz4.frame.open(final_output_path, 'wb') as lz4_out:
                shutil.copyfileobj(tar_in, lz4_out)

            print("TAR.LZ4 repackaging successful.")
        except Exception as e:
            raise Exception(f"Failed to process for {original_type} to {final_output_path}: {e}")
        finally: # Clean up temporary TARs
            if os.path.exists(temp_original_tar_path): os.remove(temp_original_tar_path)
            if os.path.exists(temp_new_patched_tar_path): os.remove(temp_new_patched_tar_path)
    else: raise ValueError(f"Unsupported original type for repackaging: {original_type}")
    if not final_output_path or not os.path.exists(final_output_path): raise Exception("Repackaging failed.")
    return final_output_path

# --- MagiskPatcher Class (remains unchanged from previous step for this subtask) ---
class MagiskPatcher:
    def __init__(self, magiskboot_exe_path, assets_dir, working_dir, options=None, logger=print):
        self.magiskboot_exe = magiskboot_exe_path; self.assets_dir = assets_dir; self.working_dir = working_dir
        self.options = options if options else {}; self.logger = logger; os.makedirs(self.working_dir, exist_ok=True)
        self.target_arch = self.options.get("TARGET_ARCH", "arm64")
        self.logger(f"MagiskPatcher: Target arch: {self.target_arch}")
        self.magisk_asset_name = f"magisk_{self.target_arch}"; self.magiskinit_asset_name = f"magiskinit_{self.target_arch}"
        self.initld_asset_name = f"initld_{self.target_arch}"
        essential = {self.magisk_asset_name: os.path.join(self.assets_dir, self.magisk_asset_name),
                     self.magiskinit_asset_name: os.path.join(self.assets_dir, self.magiskinit_asset_name)}
        for name, path in essential.items():
            if not os.path.exists(path): raise FileNotFoundError(f"MagiskPatcher: Asset '{name}' not found: {path}")
            self.logger(f"MagiskPatcher: Found asset: {path}")
        self.initld_asset_path = os.path.join(self.assets_dir, self.initld_asset_name)
        if not os.path.exists(self.initld_asset_path): self.logger(f"MagiskPatcher: Warn - Asset '{self.initld_asset_name}' not found: {self.initld_asset_path}"); self.initld_asset_path = None
        else: self.logger(f"MagiskPatcher: Found asset: {self.initld_asset_path}")
        self.stub_apk_path = os.path.join(self.assets_dir, "stub.apk")
        if not os.path.exists(self.stub_apk_path): self.logger(f"MagiskPatcher: Warn - stub.apk not found: {self.stub_apk_path}"); self.stub_apk_path = None
    def _exec_magiskboot(self, args, check_return_code=True, env_vars=None): # ... (implementation from prev step)
        cmd = [self.magiskboot_exe] + args; self.logger(f"MagiskPatcher: Executing: {' '.join(cmd)}")
        try:
            env = os.environ.copy(); env.update(env_vars or {})
            p = subprocess.Popen(cmd, cwd=self.working_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            out, err = p.communicate()
            if out: self.logger(f"MagiskPatcher (stdout): {out.strip()}")
            if err: self.logger(f"MagiskPatcher (stderr): {err.strip()}")
            if check_return_code and p.returncode != 0: raise subprocess.CalledProcessError(p.returncode, cmd, output=out, stderr=err)
            return out, err, p.returncode
        except FileNotFoundError: self.logger(f"MagiskPatcher: ERROR - magiskboot not found: {self.magiskboot_exe}"); raise
        except subprocess.CalledProcessError as e: self.logger(f"MagiskPatcher: ERROR - magiskboot failed (code {e.returncode})"); raise
    def _compress_to_xz(self, source_path, dest_path_xz): # ... (implementation from prev step)
        self.logger(f"MagiskPatcher: Compressing {source_path} to {dest_path_xz}...");
        if not os.path.exists(source_path): raise FileNotFoundError(f"Cannot compress, src missing: {source_path}")
        self._exec_magiskboot(['xz', source_path, dest_path_xz])
        if not os.path.exists(dest_path_xz): raise Exception(f"XZ compression failed, output missing: {dest_path_xz}")
        self.logger(f"MagiskPatcher: Compressed to {dest_path_xz}")
    def patch_boot_image(self, plain_boot_image_path, original_boot_img_path_for_repack_ref): # ... (implementation from prev step, detailed CPIO ops)
        self.logger(f"MagiskPatcher: Patching {plain_boot_image_path} for arch {self.target_arch}")
        local_magiskinit_path = os.path.join(self.working_dir, "magiskinit_for_ramdisk")
        shutil.copy(os.path.join(self.assets_dir, self.magiskinit_asset_name), local_magiskinit_path)
        local_magisk_path = os.path.join(self.working_dir, f"magisk_for_ramdisk_{self.target_arch}")
        shutil.copy(os.path.join(self.assets_dir, self.magisk_asset_name), local_magisk_path)
        local_initld_path, initld_xz_path, local_stub_path, stub_xz_path = None, None, None, None
        if self.initld_asset_path: local_initld_path = os.path.join(self.working_dir, "initld_for_ramdisk"); shutil.copy(self.initld_asset_path, local_initld_path)
        if self.stub_apk_path: local_stub_path = os.path.join(self.working_dir, "stub_for_ramdisk.apk"); shutil.copy(self.stub_apk_path, local_stub_path)
        magisk_xz_name_in_ramdisk = f"magisk_{self.target_arch}.xz"; magisk_xz_path = os.path.join(self.working_dir, magisk_xz_name_in_ramdisk)
        self._compress_to_xz(local_magisk_path, magisk_xz_path)
        if local_initld_path: initld_xz_path = os.path.join(self.working_dir, "init-ld.xz"); self._compress_to_xz(local_initld_path, initld_xz_path)
        if local_stub_path: stub_xz_path = os.path.join(self.working_dir, "stub.xz"); self._compress_to_xz(local_stub_path, stub_xz_path)
        internal_boot_img_path = os.path.join(self.working_dir, "boot.img"); shutil.copy(plain_boot_image_path, internal_boot_img_path)
        self._exec_magiskboot(['unpack', internal_boot_img_path])
        ramdisk_cpio_path = os.path.join(self.working_dir, "ramdisk.cpio");
        if not os.path.exists(ramdisk_cpio_path): raise FileNotFoundError(f"ramdisk.cpio missing after unpack in {self.working_dir}")
        cpio_cmds = [f'add 0750 init {local_magiskinit_path}', 'mkdir 0750 overlay.d', 'mkdir 0750 overlay.d/sbin',
                       f'add 0644 overlay.d/sbin/{magisk_xz_name_in_ramdisk} {magisk_xz_path}']
        if initld_xz_path: cpio_cmds.append(f'add 0644 overlay.d/sbin/init-ld.xz {initld_xz_path}')
        if stub_xz_path: cpio_cmds.append(f'add 0644 overlay.d/stub.xz {stub_xz_path}')
        env = {opt: "true" for opt in ["KEEPVERITY", "KEEPFORCEENCRYPT", "PATCHVBMETAFLAG", "RECOVERYMODE", "LEGACYSAR"] if self.options.get(opt)}
        for cmd in cpio_cmds: self._exec_magiskboot(['cpio', ramdisk_cpio_path, cmd], env_vars=env)
        self._exec_magiskboot(['repack', internal_boot_img_path], env_vars=env)
        files_to_clean = [local_magiskinit_path, local_magisk_path, magisk_xz_path, local_initld_path, initld_xz_path, local_stub_path, stub_xz_path]
        for f in files_to_clean:
            if f and os.path.exists(f): os.remove(f)
        patched_img_path = os.path.join(self.working_dir, "new-boot.img")
        if not os.path.exists(patched_img_path): raise Exception(f"Patched 'new-boot.img' missing in {self.working_dir}")
        self.logger(f"MagiskPatcher: Patched image: {patched_img_path}"); return patched_img_path

# --- Main CLI Handling ---
def handle_extract(args):
    print(f"Extract command: Input: {args.input}, Output: {args.output}")

def handle_patch(args):
    input_image_path = args.input
    output_directory = args.output
    plain_boot_img_prepared_path, original_type, processing_temp_dir, original_boot_img_arcname = None, None, None, None
    print(f"Patch command: Input: {input_image_path}, Output Dir: {output_directory}")

    try:
        plain_boot_img_prepared_path, original_type, processing_temp_dir, original_boot_img_arcname = \
            prepare_boot_image_for_patching(input_image_path)

        print(f"Prepared plain boot image: {plain_boot_img_prepared_path} (Type: {original_type}, Arcname: {original_boot_img_arcname})")
        print(f"Temp dir contents: {os.listdir(processing_temp_dir)}")

        actually_patched_boot_img_path = None
        if args.magisk:
            print("Magisk patch selected.")
            magisk_assets_root = os.path.join(os.getcwd(), "vendor", "magisk-assets")
            magiskboot_exe = os.path.join(magisk_assets_root, "magiskboot.exe" if os.name == 'nt' else "magiskboot")
            os.makedirs(magisk_assets_root, exist_ok=True)

            patcher_options = { "TARGET_ARCH": args.target_arch, "KEEPVERITY": args.keep_verity,
                                "KEEPFORCEENCRYPT": args.keep_forceencrypt, "PATCHVBMETAFLAG": args.patch_vbmeta_flag,
                                "RECOVERYMODE": args.recovery_mode, "LEGACYSAR": args.legacy_sar }
            print(f"MagiskPatcher options: {patcher_options}")
            magisk_patcher = MagiskPatcher(magiskboot_exe, magisk_assets_root, processing_temp_dir, patcher_options, print)
            actually_patched_boot_img_path = magisk_patcher.patch_boot_image(plain_boot_img_prepared_path, input_image_path)
            print(f"MagiskPatcher returned: {actually_patched_boot_img_path}")

        elif args.apatch:
            print("APatch selected (placeholder).")
            actually_patched_boot_img_path = plain_boot_img_prepared_path
        else:
            print("No specific patcher selected. Repackaging prepared image.")
            actually_patched_boot_img_path = plain_boot_img_prepared_path

        if actually_patched_boot_img_path and os.path.exists(actually_patched_boot_img_path):
            final_output = repackage_patched_boot_image(
                actually_patched_boot_img_path,
                input_image_path,
                original_type,
                output_directory,
                original_boot_img_arcname=original_boot_img_arcname # Pass it here
            )
            print(f"Repackaging complete. Final output: {final_output}")
        else: raise Exception("Patched image not found or not produced.")
    except Exception as e: print(f"Error in patch process: {e}")
    finally:
        if processing_temp_dir and os.path.exists(processing_temp_dir):
            print(f"Cleaning up temp dir: {processing_temp_dir}")
            shutil.rmtree(processing_temp_dir)
        else: print("No temp dir to clean or already cleaned.")

def main():
    parser = argparse.ArgumentParser(description="Windows Image Patching Tool (WIPT)")
    subparsers = parser.add_subparsers(title="Commands", dest="command", required=True)
    parser_extract = subparsers.add_parser("extract", help="Extract firmware images.")
    parser_extract.add_argument("--input", required=True); parser_extract.add_argument("--output", required=True)
    parser_extract.set_defaults(func=handle_extract)
    parser_patch = subparsers.add_parser("patch", help="Patch firmware images.")
    parser_patch.add_argument("--input", required=True); parser_patch.add_argument("--output", required=True)
    patcher_group = parser_patch.add_mutually_exclusive_group(required=False)
    patcher_group.add_argument("--magisk", action="store_true"); patcher_group.add_argument("--apatch", action="store_true")
    magisk_opts = parser_patch.add_argument_group("Magisk Options (if --magisk is used)")
    magisk_opts.add_argument("--target_arch",type=str,default="arm64",choices=["arm","arm64","x86","x64"],help="Target arch. Default: arm64.")
    magisk_opts.add_argument("--keep_verity",action="store_true"); magisk_opts.add_argument("--keep_forceencrypt",action="store_true")
    magisk_opts.add_argument("--patch_vbmeta_flag",action="store_true"); magisk_opts.add_argument("--recovery_mode",action="store_true")
    magisk_opts.add_argument("--legacy_sar",action="store_true")
    parser_patch.set_defaults(func=handle_patch)
    args = parser.parse_args()
    if hasattr(args, 'func'): args.func(args)
    else: parser.print_help()

if __name__ == "__main__":
    main()
