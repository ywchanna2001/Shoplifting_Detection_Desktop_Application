# PyInstaller build file. Build the Windows app with:
#     pyinstaller ShopGuard.spec
# The result is a folder dist/ShopGuard/ containing ShopGuard.exe.
# Put your trained model at models/best.onnx first, or the build will stop with an error.

a = Analysis(
    ["main.py"],
    datas=[
        ("models/*.onnx", "models"),
        ("shopguard/ui/assets", "shopguard/ui/assets"),
    ],
    # Training-only libraries must not end up in the installer (they add hundreds of MB).
    excludes=["torch", "torchvision", "ultralytics", "matplotlib", "tkinter", "pandas"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ShopGuard",
    console=False,  # no black console window behind the app
)
coll = COLLECT(exe, a.binaries, a.datas, name="ShopGuard")
