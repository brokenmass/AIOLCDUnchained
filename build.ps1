maturin build --release
pip install ./target/wheels/q565_rust-0.1.0-cp311-none-win_amd64.whl --force-reinstall
pyinstaller --noconfirm --onefile --windowed --icon "./icon.ico" --add-data "./fonts;fonts/" --add-data "./images;images/" --add-data "./SignalRGBPlugin;SignalRGBPlugin/" "./signalrgb.py"