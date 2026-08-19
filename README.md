# MSMR-Explorer
Game Archive File Explorer for Marvel's Spider-Man: Remastered

[NexusMods Page](https://www.nexusmods.com/marvelsspidermanremastered/mods/6258)

# Compiling to EXE using PyInstaller
I used this command-line:

```
pyinstaller --onedir --icon=msmr_explorer.ico --add-data "gui.ui;." --add-data "redirect_asset.ui;." --add-data "hashes.txt;." --add-data "msmr_explorer.ico;." --exclude-module PySide6 --name "MSMR Explorer" main.py
```



# Credits & References

`Tkachov's MSMR Modding Tool for "hashes.txt":`
[Modding Tool](https://www.nexusmods.com/marvelsspidermanremastered/mods/4395)


`Tkachov's ALERT for "crc64.py":`
[crc64.py](https://github.com/Tkachov/ALERT/blob/main/dat1lib/crc64.py)
