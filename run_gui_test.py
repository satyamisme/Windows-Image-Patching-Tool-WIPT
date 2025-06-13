import tkinter as tk
from wipt_gui import WiptGuiApp
import os

# Ensure wipt.py is importable by being in the same directory or PYTHONPATH

def auto_run_patch(app_instance):
    print("AUTO_RUN: Setting paths and options...")
    app_instance.input_image_path.set(os.path.abspath("dummy_boot.img"))
    app_instance.output_dir_path.set(os.path.abspath("test_output_gui_integration"))
    app_instance.output_filename.set("dummy_boot_gui_patched.img") # Suggestion
    app_instance.patcher_choice.set("Magisk")
    app_instance.target_arch.set("arm64")
    # Other options like keep_verity can be set if needed for deeper testing

    print("AUTO_RUN: Triggering start_patching_thread...")
    app_instance.start_patching_thread()

    # Add a short delay then attempt to close, to allow patching thread to log
    app_instance.root.after(5000, app_instance.root.destroy) # 5 seconds for patching logs

if __name__ == '__main__':
    if not os.path.exists("wipt.py"):
        print("ERROR: wipt.py not found. Make sure it's in the current directory.")
        exit(1)
    if not os.path.exists("dummy_boot.img"):
        print("ERROR: dummy_boot.img not found. Create it first.")
        exit(1)
    if not os.path.exists("vendor/magisk-assets/magiskboot"):
        print("ERROR: vendor/magisk-assets/magiskboot placeholder not found.")
        exit(1)


    root = tk.Tk()
    app = WiptGuiApp(root)
    # Schedule the auto_run_patch after GUI is initialized
    root.after(1000, lambda: auto_run_patch(app)) # 1 second delay
    root.mainloop()
    print("AUTO_RUN: GUI mainloop finished.")
