import sys
import os
from pathlib import Path

import ctypes
import crc64

from helpers import *
from toc import *
from dsar import *

from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMenu, QAbstractItemView
from PyQt6.QtGui import QStandardItem, QStandardItemModel, QCursor
from PyQt6.QtCore import QSortFilterProxyModel, Qt, pyqtSignal, QThread, QObject

BASE_DIR = Path(sys.executable).parent

gui_path = BASE_DIR / "_internal" / "gui.ui"
hashes_path = BASE_DIR / "_internal" / "hashes.txt"

def resource_path(relative_path):
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

class TreeWorker(QObject):
    finished = pyqtSignal(dict)

    def __init__(self, entries, archive_name):
        super().__init__()
        self.entries = entries
        self.archive_name = archive_name

    def run(self):
        tree = {}
        
        for entry in self.entries:

            if entry["ArchiveName"] != self.archive_name:
                continue

            entry_name = entry["EntryName"]

            if entry_name is None:
                continue

            parts = [
                p for p in entry_name.replace("\\", "/").split("/")
                if p
            ]

            current = tree

            for part in parts:
                current = current.setdefault(part, {})

        self.finished.emit(tree)
        
        
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        uic.loadUi(resource_path("gui.ui"), self)
        
        # Dark Stylesheet
        self.dark_style = """
            QWidget {
                background-color: #202020;
                color: white;
            }

            QTreeView::item:selected {
                background-color: ACCENT_COLOR;
            }
            
            QTableView {
                background-color: #252525;
                color: white;
                border: 1px solid #444444;
            }

            QHeaderView::section {
                background-color: #303030;
                color: white;
            }

            QLineEdit {
                background-color: #303030;
                color: white;
                border: 1px solid #555555;
            }

            QPushButton {
                background-color: #303030;
                color: white;
                border: 1px solid #555555;
            }

            QMenu {
                background-color: #303030;
                color: white;
            }

            QMenu::item:selected {
                background-color: #505050;
            }
        """
        
        
        
        # Connecting Menu Buttons
        self.actionOpen_TOC_file.triggered.connect(self.OpenTOC)
        self.actionOpen_Game_Archive_File_s.triggered.connect(self.OpenDSAR)
        
        
        # ArchiveTree and AssetTable Models
        self.archive_model = QStandardItemModel()
        self.archive_model.setHorizontalHeaderLabels(["Archives"])
        self.archiveTree.setModel(self.archive_model)
        
        self.archiveTree.expanded.connect(self.OnTreeExpanded) # Populate each archive item and subitems on expanding the arrow
        
        self.asset_source_model = QStandardItemModel()
        self.asset_source_model.setHorizontalHeaderLabels( ["AssetIndex", "AssetHash", "AssetName", "Archive", "AssetOffset", "AssetSize"] )
        
        self.asset_model = QSortFilterProxyModel()
        self.asset_model.setSourceModel(self.asset_source_model)
        self.asset_model.setFilterKeyColumn(-1) # Filter all columns instead of defaulting to first column
        self.asset_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive) # Case-Insensitive filtering

        self.assetTable.setModel(self.asset_model)
        
        # Context Menu
        self.archiveTree.customContextMenuRequested.connect(   
        lambda: self.show_context_menu_tree(self.ExtractAssetFromTree, self.ExtractArchiveFromTree), 
        )
        
        self.assetTable.customContextMenuRequested.connect(lambda: self.show_context_menu_table(self.ExtractAssetFromTable, self.RedirectAssetFromTableGUI) )
        
        # SearchBox
        self.searchBox.textChanged.connect(self.asset_model.setFilterFixedString) # Search as you type
        self.searchBox.setPlaceholderText("Search...") # Placeholder text
        
        # Disable Editing on Double-Click
        #self.archiveTree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        #self.assetTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Dark Mode Checkbox
        self.darkModeCheckBox.toggled.connect(self.toggle_dark_mode)
        
        # Accent Color Combobox
        self.accentComboBox.currentTextChanged.connect(self.change_accent)
        
        # Create Mod Archive PushButton
        self.createModArchiveButton.clicked.connect(self.create_mod_archive)
    

    def OpenTOC(self):
        self.toc_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open TOC",
            "",
            "TOC files (*)"
        )

        if not self.toc_path:
            return  # User cancelled

        print(self.toc_path)
        
        with open(self.toc_path, "rb") as f:
            self.toc = TOC()
            
            self.toc.ReadCompressedTOC(f)
            
            if self.toc.Magic != b"\xAF\x12\xAF\x77":
                return
            
            self.toc.DecompressTOC()
            
            decompressed_toc_bytes_object = BytesIO(self.toc.DecompressedTOC)
            
            self.toc.ReadDecompressedTOC(decompressed_toc_bytes_object)
            
            
    def OpenDSAR(self):
        self.dsar_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Game Archive File(s)",
            "",
            "Game Archive File(s) (*)"
        )

        if not self.dsar_paths:
            return  # User cancelled
        
        
        
        
        
        self.hashes = {}
        with open(resource_path("hashes.txt"), "r", encoding="utf-8") as r:
            for line in r:
                hash_value, filename, num_duplicates = line.strip().split(",", 2)
                self.hashes[int(hash_value, 16)] = filename
        
        self.Entries = []
        for path in self.dsar_paths:
            print(path)
            
            archive_name = os.path.basename(path) # Extracts a00s044.ar from arhive path for example
            archive_number = self.toc.ArchivesIndicesByNames[archive_name] # Gets 044 for a00s044.ar for example
            
            print("AssetIDs entries:", len(self.toc.AssetIDs))
            print("OffsetsMap entries:", len(self.toc.OffsetsMap))
            print("SizeEntries entries:", len(self.toc.SizeEntries))

            for entry in self.toc.SizeEntries:
                entry_index = entry["Index"]
                entry_size = entry["Value"]
                
                archive_entry = self.toc.OffsetsMap[entry_index]
                
                entry_archive_index = archive_entry["ArchiveIndex"]
                entry_offset = archive_entry["OffsetInArchive"]
                
                entry_id = self.toc.AssetIDs[entry_index]
                
                if entry_archive_index == archive_number:
                    entry_name = self.hashes.get(entry_id)
                    
                    self.Entries.append( {"ArchiveName": archive_name, "EntryName": entry_name} )
                    
                    self.PopulateAssetTable(entry_index, entry_id, entry_name, archive_name, entry_offset, entry_size)
        
        self.PopulateArchiveTree()
        
        
    def PopulateArchiveTree(self):
        root = self.archive_model.invisibleRootItem()
    
        archive_items = {}
        for dsar_path in self.dsar_paths:

            archive_name = os.path.basename(dsar_path)

            item = QStandardItem(archive_name)
            
            # Dummy child so the ▶ arrow appears
            dummy = QStandardItem("")
            item.appendRow(dummy)

            root.appendRow(item)
            
        

    
    
    def OnTreeExpanded(self, index):
        item = self.archive_model.itemFromIndex(index)

        if item is None:
            return

        # Remove dummy child
        if item.rowCount() == 1 and item.child(0, 0).text() == "":
            item.removeRow(0)

        archive_name = item.text()

        self.LoadArchiveTree(archive_name, item)
    
        
    def LoadArchiveTree(self, archive_name, parent_item):
        self.thread = QThread()
        self.worker = TreeWorker(self.Entries, archive_name)

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        self.worker.finished.connect(
            lambda tree: self.BuildTree(parent_item, tree)
        )

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()
        
            
    def BuildTree(self, parent, tree):
        for name, children in tree.items():

            item = QStandardItem(name)
            item.setEditable(False)

            parent.appendRow(item)

            self.BuildTree(item, children)
            
        
    def PopulateAssetTable(self, asset_index, asset_hash, asset_name, archive_name, asset_offset, asset_size):
        
        
        self.asset_source_model.appendRow([
                QStandardItem(str(asset_index)),
                QStandardItem( f'{asset_hash:016X}' ), # Asset ID is used as hash
                QStandardItem(asset_name),
                QStandardItem(archive_name),
                QStandardItem(f"0x{asset_offset:X}"),
                QStandardItem(str(asset_size))
            ])
        
        
        
    def show_context_menu_tree(self, extract_function, extract_archive_function):
        menu = QMenu()

        extract_action = menu.addAction("Extract Asset...")
        extract_archive_action = menu.addAction("Extract Archive...")
        
        action = menu.exec(QCursor.pos())

        if action == extract_action:
            extract_function()
            
        elif action == extract_archive_action:
            extract_archive_function()
                
    
    def show_context_menu_table(self, extract_function, redirect_asset_function):
        menu = QMenu()

        extract_action = menu.addAction("Extract Asset...")
        redirect_action = menu.addAction("Redirect Asset...")

        action = menu.exec(QCursor.pos())

        if action == extract_action:
            extract_function()
            
        if action == redirect_action:
            redirect_asset_function()

        
        
    def ExtractAsset(self, archive, asset_name, asset_offset, asset_size):
        for path in self.dsar_paths:
            if os.path.basename(path) == archive:
                archive_path = path 
        
        output_dir = os.path.dirname(archive_path)
        
        
        asset_dir = os.path.join(output_dir, f"{archive}_unpacked")
        
        with open(archive_path, "rb") as f:
                self.dsar = DSAR()
                
                IsDSAR = (f.read(4) == b"DSAR") # This advances the file pointer by 4 !
                f.seek(0) # Seek to beginning again !
                if IsDSAR:
                    self.dsar.ReadDSARHeader(f)
                    self.dsar.ReadBlockTable(f)
                
                
                asset_to_write = self.dsar.GetAsset( f, int(asset_offset, 16), int(asset_size), IsDSAR)
                
                
        os.makedirs(asset_dir, exist_ok=True)

        output_path = os.path.join(
            asset_dir,
            asset_name.replace("\\", "_").replace("/", "_")
        )

        with open(output_path, "wb") as out:
            
            out.write(asset_to_write)
                
    
    
    def ExtractAssetFromTable(self):
        index = self.assetTable.currentIndex()

        if not index.isValid():
            return

        row = index.row()

        asset_index = self.asset_model.index(row, 0).data()
        asset_name = self.asset_model.index(row, 2).data()
        archive = self.asset_model.index(row, 3).data()
        asset_offset = self.asset_model.index(row, 4).data()
        asset_size = self.asset_model.index(row, 5).data()
        
        if asset_name == "" or asset_name is None:
                asset_name = self.asset_model.index(row, 1).data() # Use Asset Hash Instead
                
        self.ExtractAsset(archive, asset_name, asset_offset, asset_size)
        
    
    def ExtractAssetFromTree(self):
        index = self.archiveTree.currentIndex()
        
        if not index.isValid():
            return
            
        asset_name = index.data()
        
        wanted_asset_row = None
        for r in range(self.asset_model.rowCount() ):
            if asset_name in self.asset_model.index(r, 2).data():
                wanted_asset_row = r
        
        if wanted_asset_row is None:
            return
        
        asset_index = self.asset_model.index(wanted_asset_row, 0).data()
        asset_name = self.asset_model.index(wanted_asset_row, 2).data()
        archive = self.asset_model.index(wanted_asset_row, 3).data()
        asset_offset = self.asset_model.index(wanted_asset_row, 4).data()
        asset_size = self.asset_model.index(wanted_asset_row, 5).data()
        
        if asset_name == "" or asset_name is None:
            asset_name = self.asset_model.index(wanted_asset_row, 1).data() # Use Asset Hash Instead
        
        self.ExtractAsset(archive, asset_name, asset_offset, asset_size)
        
        
    def ExtractArchiveFromTree(self):
        index = self.archiveTree.currentIndex()
        
        if not index.isValid():
            return
            
        archive_name = index.data()
        
        wanted_asset_rows = []
        for r in range(self.asset_model.rowCount() ):
            if archive_name in self.asset_model.index(r, 3).data():
                wanted_asset_rows.append(r)
        
        if not wanted_asset_rows: # List is empty
            return
        
        for w in wanted_asset_rows:
            asset_index = self.asset_model.index(w, 0).data()
            asset_name = self.asset_model.index(w, 2).data()
            archive = self.asset_model.index(w, 3).data()
            asset_offset = self.asset_model.index(w, 4).data()
            asset_size = self.asset_model.index(w, 5).data()
            
            if asset_name == "" or asset_name is None:
                asset_name = self.asset_model.index(w, 1).data() # Use Asset Hash Instead
            
            self.ExtractAsset(archive, asset_name, asset_offset, asset_size)
        
        
    
    def set_title_bar_dark(self, dark):
        hwnd = int(self.winId())

        value = ctypes.c_int(1 if dark else 0)

        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            20,  # DWMWA_USE_IMMERSIVE_DARK_MODE
            ctypes.byref(value),
            ctypes.sizeof(value)
        )
    
    def toggle_dark_mode(self, checked):
        if checked:
            self.set_title_bar_dark(True)
            self.setStyleSheet(self.dark_style)
            
        else:
            self.set_title_bar_dark(False)
            self.setStyleSheet("")
            
            
    def change_accent(self, color):
        if color == "Blue":
            accent = "#3d6fa5"
        elif color == "Purple":
            accent = "#805ad5"
        elif color == "Green":
            accent = "#38a169"
        elif color == "Red":
            accent = "#e53e3e"

        self.setStyleSheet(
            self.dark_style.replace("ACCENT_COLOR", accent)
        )
        
        
    
    
    def create_mod_archive(self, _):
        self.mod_folder = QFileDialog.getExistingDirectory(
            self,
            "Select Mod Folder"
        )
        
        
        if not self.mod_folder:
            return
        
        filepaths = []
        for root, dirs, files in os.walk(self.mod_folder):
            for file in files:
                file_path = os.path.join(root, file)
                print(file_path)
                
                filepaths.append(file_path)
        
        
        

        # Build Section 0 [ArchiveNames]
        ArchiveName = os.path.basename(self.mod_folder)
        
        # ArchivesMap
        self.toc.Sections[0]["SectionData"] += b"\x00" * 8 # Install Bucket, Chunkmap
        self.toc.Sections[0]["SectionData"] += ArchiveName.encode("utf-8") # Archive Name
        self.toc.Sections[0]["SectionData"] += b"\x00" * (64 - len(ArchiveName)) # Rest of 64 bytes
        
        AssetOffset = 0
        
        offset = 0
        filepaths_redirect = []
        for filepath in filepaths:
            print("FILE:", filepath)
            size = os.path.getsize(filepath)

            if "_redirect" in os.path.basename(filepath):
                filepaths_redirect.append( {"redirect_filepath": filepath, "redirect_offset": offset, "redirect_size": size} )

            offset += size
            
        print(len(filepaths_redirect))
             
            
            
        
        
        BaseNames = []
        for filepath in filepaths:
            basename = os.path.basename(filepath)
            basename = basename.replace("_", "/")
            basename = basename.replace("//", "_")
            
            BaseNames.append(basename)
        
        # Reorder AssetIDs Ascendingly
        AssetIDs = self.toc.Sections[1]["SectionData"]

        ExistingIDs = [
            int.from_bytes(
                AssetIDs[i:i+8],
                "little"
            )
            for i in range(0, len(AssetIDs), 8)
        ]

        AllIDs = []

        # Existing AssetIDs
        for OriginalIndex, ID in enumerate(ExistingIDs):
            AllIDs.append({
                "ID": ID,
                "OriginalIndex": OriginalIndex,
                "New": False
            })

        # New AssetIDs
        NewAssets = []
        NewAssetsRaw = []
        for i, filepath in enumerate(filepaths):
            basename = BaseNames[i]
            print(basename)
            
            if "/redirect" in basename:
                continue
                
            
            ID = crc64.hash(basename)

            AllIDs.append({
                "ID": ID,
                "OriginalIndex": i,
                "New": True
            })
            
            if "/raw" in basename:
                basename = basename.replace("/raw", "")
                ID = crc64.hash(basename)
                
                NewAssetsRaw.append({
                "ID": ID,
                "OriginalIndex": i,
                "New": True
            })
            
            else:
                NewAssets.append({
                "ID": ID,
                "OriginalIndex": i,
                "New": True
            })
           
        
        
        # Spans
        section_data_bytearray = bytearray(self.toc.Sections[5]["SectionData"])
        
        Spans = []

        for k in range(0, len(section_data_bytearray), 8):

            FirstAssetIndex = struct.unpack(
                "<I",
                section_data_bytearray[k:k+4]
            )[0]

            Count = struct.unpack(
                "<I",
                section_data_bytearray[k+4:k+8]
            )[0]

            Spans.append({
                "FirstAssetIndex": FirstAssetIndex,
                "Count": Count
            })
        
     
        # Rebuild span indices.
        #
        # The spans stay in the same order.
        # Their counts stay the same except Span 0, 1
        # which receives all new assets, new raw assets

        NewSpans = []
        NewAllIDs = []
        for span_index, span in enumerate(Spans):

            old_first = span["FirstAssetIndex"]
            old_count = span["Count"]

            span_entries = AllIDs[
                old_first:old_first + old_count
            ]

            if span_index == 0:

                span_entries = span_entries + NewAssets # Add DAT1 assets like sd textures here in the first even span

                span_entries.sort(
                    key=lambda x: x["ID"]
                )
                
            elif span_index == 1:
                span_entries = span_entries + NewAssetsRaw # Add raw assets like hd textures here in the first odd span
                
                span_entries.sort(
                    key=lambda x: x["ID"]
                )
                
            NewAllIDs.extend(span_entries)
            
        
        # Rebuild span indices
        NewSpans = []

        current_index = 0

        for i, span in enumerate(Spans):

            old_count = span["Count"]

            if i == 0:

                # Span 0 received all new assets
                new_count = old_count + len(NewAssets)
            
            elif i == 1:
                # Span 1 received all new raw assets
                new_count = old_count + len(NewAssetsRaw)
                
            else:

                # Other spans keep their original count
                new_count = old_count

            NewSpans.append({
                "FirstAssetIndex": current_index,
                "Count": new_count
            })

            current_index += new_count
    
        # Rebuild Section 5 (Spans)
        New = bytearray()

        for span in NewSpans:

            New += struct.pack(
                "<I",
                span["FirstAssetIndex"]
            )

            New += struct.pack(
                "<I",
                span["Count"]
            )

        self.toc.Sections[5]["SectionData"] = New
        
        
        AllIDs = NewAllIDs

        # Add a new dictionary key ("NewIndex") which simply has the new index for every ID which is simply their current index in AllIDs list
        for NewIndex, entry in enumerate(AllIDs):
            entry["NewIndex"] = NewIndex
            
            
        # Get whole entries of already existing AssetIDs
        ExistingAssetsInfoByOriginalIndex = {
            entry["OriginalIndex"]: entry
            for entry in AllIDs
            if not entry["New"]
        }
        
        # Get whole entries of all new AssetIDss
        NewAssetsInfoByOriginalIndex = {
            entry["OriginalIndex"]: entry
            for entry in AllIDs
            if entry["New"]
        }
        
        # Build final AssetID SectionData and Rebuild Section 1 (AssetIDs)
        NewSorted = bytearray()

        for entry in AllIDs:
            NewSorted += struct.pack("<Q", entry["ID"])

        self.toc.Sections[1]["SectionData"] = NewSorted
        
        
        ConcatenatedArchive = b""
        new_entries = []
        for i, filepath in enumerate(filepaths):
            basename = BaseNames[i]

            with open(filepath, "rb") as f:
                data = f.read()

            ConcatenatedArchive += data

            if "/redirect" in basename:
                AssetOffset += os.path.getsize(filepath)
                continue

            asset_info = NewAssetsInfoByOriginalIndex[i]

            asset_index = asset_info["NewIndex"]
            is_new = asset_info["New"]
            
            size = os.path.getsize(filepath)

            new_entries.append({
                "Index": asset_index,
                "Size": size,
                "ArchiveIndex": (len(self.toc.Sections[0]["SectionData"]) // 72) - 1,
                "Offset": AssetOffset,
                "New": is_new
            })

            AssetOffset += size
        
        # Rebuild Section 2 (Size Entries)
        # SizeEntries
        # SizeEntries
        section_data_bytearray = bytearray(
            self.toc.Sections[2]["SectionData"]
        )

        section_chunks = [
            section_data_bytearray[i:i+12]
            for i in range(0, len(section_data_bytearray), 12)
            if len(section_data_bytearray[i:i+12]) == 12
        ]

        # Final SizeEntries indexed by NEW AssetID index
        NewSizeEntries = [None] * len(AllIDs)


        # Move existing SizeEntries:
        # OLD AssetID index -> NEW AssetID index
        for chunk in section_chunks:

            Always_1, Size, old_index = struct.unpack("<III", chunk)

            if old_index not in ExistingAssetsInfoByOriginalIndex:
                print("WARNING: SizeEntry references unknown old index:", old_index)
                continue

            new_index = ExistingAssetsInfoByOriginalIndex[old_index]["NewIndex"]

            NewSizeEntries[new_index] = struct.pack(
                "<III",
                1,
                Size,
                new_index
            )


        # Add NEW assets
        for entry in new_entries:

            new_index = entry["Index"]

            NewSizeEntries[new_index] = struct.pack(
                "<III",
                1,
                entry["Size"],
                new_index
            )

        # Rebuild Section 2
        New = bytearray()

        for entry in NewSizeEntries:

            if entry is None:
                continue

            New += entry

        self.toc.Sections[2]["SectionData"] = New
        
        # Rebuild Section 4 (Offsets)
        # Offsets
        # Offsets currently correspond to OLD AssetID indices
        section_data_bytearray = bytearray(self.toc.Sections[4]["SectionData"])

        section_chunks = [
            section_data_bytearray[i:i+8]
            for i in range(0, len(section_data_bytearray), 8)
        ]
        
        # Create the final offsets array.
        # Its position must correspond to the NEW AssetID index
        NewOffsets = [None] * len(AllIDs)

        # Move existing offsets from old index -> new index
        for old_index, chunk in enumerate(section_chunks):

            if old_index not in ExistingAssetsInfoByOriginalIndex:
                continue

            new_index = ExistingAssetsInfoByOriginalIndex[old_index]["NewIndex"]

            NewOffsets[new_index] = chunk
        
        
        # Put NEW asset offsets into their NEW indices
        for entry in new_entries:

            new_index = entry["Index"]

            NewOffsets[new_index] = struct.pack(
                "<II",
                entry["ArchiveIndex"],
                entry["Offset"]
            )

        # Rebuild Section 4
        New = bytearray()

        for offset in NewOffsets:
            New += offset

        self.toc.Sections[4]["SectionData"] = New
        
        # -------------------------------------------------------------
        # Write New TOC
        # -------------------------------------------------------------
        
        ModArchiveAndTOCFolder = r"ModArchiveAndTOC"
        output_path = os.path.join(os.path.dirname(self.mod_folder) , ModArchiveAndTOCFolder)
        
        os.makedirs(output_path, exist_ok=True)
        
        with open(f'{output_path}\\{ArchiveName}', "wb") as out:
            out.write(ConcatenatedArchive)
            
        buffer = BytesIO()
        self.toc.WriteDecompressedTOC(buffer)
        self.toc.RewriteDecompressedTOC(buffer)
        
        self.toc.DecompressedTOC = buffer.getvalue()
        
        self.toc.CompressTOC()
        
        with open(f'{output_path}\\toc', "wb") as out:
            out.write(b"\xAF\x12\xAF\x77")
            out.write( struct.pack("<I", len(self.toc.DecompressedTOC)) )
            out.write(self.toc.CompressedTOC)
            
        # --------------------------------------------------------------
        # Redirect Assets that have "_redirect" in their basenames
        # --------------------------------------------------------------
        # Open New TOC first, so it has the modified stuff like the new ArchiveName Entry if user created a New Mod Archive
        self.OpenTOC()
        
        # Open DSAR Archive second, so it builds the asset table of the archive from which we will redirect the asset
        self.OpenDSAR()
        
        # Then Redirect
        self.RedirectAssetModArchive(self.mod_folder, filepaths_redirect)
        
        
    def RedirectAssetFromTableGUI(self):
        mod_folder = QFileDialog.getExistingDirectory(
            self,
            "Select Mod Folder"
        )

        if not mod_folder:
            return

        wanted_files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Game Assets for Redirection (Replacement)",
            "",
            "Game Asset File (*)"
        )

        if not wanted_files:
            return
            
        filepaths = []
        for root, dirs, files in os.walk(mod_folder):
            for file in files:
                file_path = os.path.join(root, file)
                print(file_path)
                
                filepaths.append(file_path)
                
                
        offset = 0
        filepaths_redirect = []

        for filepath in filepaths:
            print("FILE:", filepath)

            size = os.path.getsize(filepath)
            basename = os.path.basename(filepath)

            if "_redirect" in basename:
                for wanted_file in wanted_files:
                    if os.path.basename(wanted_file) == basename:
                        filepaths_redirect.append({
                            "redirect_filepath": filepath,
                            "redirect_offset": offset,
                            "redirect_size": size
                        })
                        break

            offset += size

        self.RedirectAsset(mod_folder, filepaths_redirect)
    
    def RedirectAsset(self, mod_folder, filepaths_redirect):

        # Ask once which archive contains the redirected assets
        dialog = RedirectAssetDialog()

        if dialog.exec() == QDialog.rejected:
            return
            
        else:
            for file_redirect in filepaths_redirect:
                print(file_redirect["redirect_filepath"])
                
                redirect_offset = file_redirect["redirect_offset"]
                redirect_size = file_redirect["redirect_size"]
                
                archive_name_redirect = dialog.ui.archiveNameLineEdit.text().strip()
                archive_index_redirect = self.toc.ArchivesIndicesByNames[archive_name_redirect]
                
                index = self.assetTable.currentIndex()
            
                if not index.isValid():
                    return
                    
                asset_name = index.data()
                asset_name = asset_name.replace("\\", "/")
                
                wanted_asset_row = index.row()
                
                asset_index = self.asset_model.index(wanted_asset_row, 0).data()
                archive_name_original = self.asset_model.index(wanted_asset_row, 3).data()
                asset_offset = self.asset_model.index(wanted_asset_row, 4).data()
                asset_size = self.asset_model.index(wanted_asset_row, 5).data()
                archive_index_original = self.toc.ArchivesIndicesByNames[archive_name_original]

                # Offsets Section
                location = int(asset_index) * 8
                print("Offset location:", location)
                section_data_bytearray = bytearray(self.toc.Sections[4]["SectionData"]) # Bytearray cause it is mutable (could be modified in place) unlike Bytes
                
                        
                section_data_bytearray[location: location + 8] = struct.pack("<I", archive_index_redirect) + struct.pack("<I", redirect_offset)
            
                
                self.toc.Sections[4]["SectionData"] = section_data_bytearray
                
                # SizeEntries Section
                location = int(asset_index) * 12
                print("SizeEntry location:", location)
                section_data_bytearray = bytearray(self.toc.Sections[2]["SectionData"]) # Bytearray cause it is mutable (could be modified in place) unlike Bytes
                
                        
                section_data_bytearray[location: location + 12] = struct.pack("<I", 1) + struct.pack("<I", redirect_size) + struct.pack("<I", int(asset_index))
            
                
                self.toc.Sections[2]["SectionData"] = section_data_bytearray
                

                buffer = BytesIO()
                self.toc.WriteDecompressedTOC(buffer)
                self.toc.RewriteDecompressedTOC(buffer)
                
                self.toc.DecompressedTOC = buffer.getvalue()
                
                self.toc.CompressTOC()
                
                ModArchiveAndTOCFolder = r"ModArchiveAndTOC"
                output_path = os.path.join(os.path.dirname(mod_folder) , ModArchiveAndTOCFolder)
                
                os.makedirs(output_path, exist_ok=True)
                
                print("About to write TOC")
                with open(f'{output_path}\\toc', "wb") as out:
                    out.write(b"\xAF\x12\xAF\x77")
                    out.write( struct.pack("<I", len(self.toc.DecompressedTOC)) )
                    out.write(self.toc.CompressedTOC)
                    print("TOC Written")
        
        
        
    def RedirectAssetModArchive(self, mod_folder, filepaths_redirect):

        # Ask once which archive contains the redirected assets
        dialog = RedirectAssetDialog()

        if dialog.exec() == QDialog.rejected:
            return
        
        else:
            for file_redirect in filepaths_redirect:
                archive_name_redirect = dialog.ui.archiveNameLineEdit.text().strip()
                archive_index_redirect = self.toc.ArchivesIndicesByNames[archive_name_redirect]
                
                print(file_redirect["redirect_filepath"])
                
                redirect_offset = file_redirect["redirect_offset"]
                redirect_size = file_redirect["redirect_size"]
                redirect_name = os.path.basename(file_redirect["redirect_filepath"])
                
                if "_redirect_localization" in redirect_name:
                    continue
                
                redirect_name = redirect_name.replace("_", "/").replace("//", "_").replace("\\", "/").replace("/redirect", "")
                print(redirect_name)
                
                
                wanted_asset_row = None
                for r in range( self.asset_model.rowCount() ):
                    if redirect_name in self.asset_model.index(r, 2).data() or redirect_name.replace("/", "\\") in self.asset_model.index(r, 2).data():
                        wanted_asset_row = r
                
                if not wanted_asset_row:
                    return

                asset_index = self.asset_model.index(wanted_asset_row, 0).data()
                archive_name_original = self.asset_model.index(wanted_asset_row, 3).data()
                asset_offset = self.asset_model.index(wanted_asset_row, 4).data()
                asset_size = self.asset_model.index(wanted_asset_row, 5).data()
                archive_index_original = self.toc.ArchivesIndicesByNames[archive_name_original]

                # Offsets Section
                location = int(asset_index) * 8
                print("Offset location:", location)
                section_data_bytearray = bytearray(self.toc.Sections[4]["SectionData"]) # Bytearray cause it is mutable (could be modified in place) unlike Bytes
                
                        
                section_data_bytearray[location: location + 8] = struct.pack("<I", archive_index_redirect) + struct.pack("<I", redirect_offset)
            
                
                self.toc.Sections[4]["SectionData"] = section_data_bytearray
                
                # SizeEntries Section
                location = int(asset_index) * 12
                print("SizeEntry location:", location)
                section_data_bytearray = bytearray(self.toc.Sections[2]["SectionData"]) # Bytearray cause it is mutable (could be modified in place) unlike Bytes
                
                        
                section_data_bytearray[location: location + 12] = struct.pack("<I", 1) + struct.pack("<I", redirect_size) + struct.pack("<I", int(asset_index))
            
                
                self.toc.Sections[2]["SectionData"] = section_data_bytearray
                

                buffer = BytesIO()
                self.toc.WriteDecompressedTOC(buffer)
                self.toc.RewriteDecompressedTOC(buffer)
                
                self.toc.DecompressedTOC = buffer.getvalue()
                
                self.toc.CompressTOC()
                
                ModArchiveAndTOCFolder = r"ModArchiveAndTOC"
                output_path = os.path.join(os.path.dirname(mod_folder) , ModArchiveAndTOCFolder)
                
                os.makedirs(output_path, exist_ok=True)
                
                print("About to write TOC")
                with open(f'{output_path}\\toc', "wb") as out:
                    out.write(b"\xAF\x12\xAF\x77")
                    out.write( struct.pack("<I", len(self.toc.DecompressedTOC)) )
                    out.write(self.toc.CompressedTOC)
                    print("TOC Written")
                
                

from PyQt6.QtWidgets import QDialog
from redirect_asset import Ui_Dialog


class RedirectAssetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)
        
        
        
app = QApplication(sys.argv)

window = MainWindow()
window.show()

sys.exit(app.exec())

        
        