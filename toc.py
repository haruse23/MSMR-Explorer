from helpers import *
import zlib
import sys
import os
from dsar import *

from io import BytesIO

ENDIANNESS = "<" # Little

class TOC():
    def __init__(self):
        self.Magic = b"\x00" * 4
        self.UncompressedLength = 0
        
        self.CompressedTOC = b""
        self.DecompressedTOC = b""
        
    def ReadCompressedTOC(self, f):
        self.Magic = f.read(4) # AF 12 AF 77
        self.UncompressedLength = read_uint(f, ENDIANNESS)
        self.CompressedTOC = f.read()
    
    def DecompressTOC(self):
        print(self.CompressedTOC[0:2])
        
        zlib_decompressor = zlib.decompressobj()
        self.DecompressedTOC = zlib_decompressor.decompress(self.CompressedTOC)
        
        with open("file.decompressed", "wb") as out:
            out.write(self.DecompressedTOC)
        
    
    def ReadDecompressedTOC(self, f):
        self.MagicDAT1 = f.read(4) # DAT1
        self.TOCType = f.read(4) # 06 E0 B8 51
        self.SizeDAT1 = read_uint(f, ENDIANNESS)
        self.SectionsCount = read_ushort(f, ENDIANNESS)
        self.UnknownsCount = read_ushort(f, ENDIANNESS)
        
        self.Sections = []
        for i in range(self.SectionsCount):
            Tag = f.read(4)
            Offset = read_uint(f, ENDIANNESS)
            Size = read_uint(f, ENDIANNESS)

            self.Sections.append( {"Tag": Tag, "Offset": Offset, "Size": Size} )
            
        unknowns = f.read(self.UnknownsCount * 8)

        # SmallestOffset = min(section["Offset"] for section in self.Sections)
    
        String = read_cstring(f) # ArchiveTOC
        
        align(16, f, f.tell()) # 16-byte alignment skipped
        
        
        for section in self.Sections:
            offset = section["Offset"]
            
            f.seek(offset)
            
            tag = section["Tag"]
            size = section["Size"]
            
            print(size)
            if tag == b"\xF0\xBF\x8A\x39": # ArchivesMapSection
                entry_count = size // 72 # 72 bytes per entry
                
                self.ArchivesIndicesByNames = {}
                for j in range(entry_count):
                    install_bucket = read_uint(f, ENDIANNESS)
                    chunk_map = read_uint(f, ENDIANNESS)
                    archive_name = f.read(64)
                    
                    archive_name_str = archive_name.decode("utf-8").rstrip("\x00")
                    
                    self.ArchivesIndicesByNames[archive_name_str] = j
                    
                
                f.seek(offset)
                section["SectionData"] = f.read(72 * entry_count)
                print(len(section["SectionData"]))
                
            if tag == b"\x8A\x7B\x6D\x50": # AssetIDsSection
                entry_count = size // 8 # Each ID is 8 bytes
                
                self.AssetIDs = []
                for j in range(entry_count):
                    self.AssetIDs.append( read_uint64(f, ENDIANNESS) )
                
                f.seek(offset)
                section["SectionData"] = f.read(8 * entry_count)
                print(len(section["SectionData"]))
                
            if tag == b"\x61\xF4\xBC\x65": # SizeEntriesSection
                entry_count = size // 12 # 12 bytes per entry
                
                self.SizeEntries = []
                for j in range(entry_count):
                    always1 = read_uint(f, ENDIANNESS) # Always 01 00 00 00
                    value = read_uint(f, ENDIANNESS) 
                    index = read_uint(f, ENDIANNESS)
                    
                    self.SizeEntries.append( {"Value": value, "Index": index} )
                
                f.seek(offset)
                section["SectionData"] = f.read(12 * entry_count)
                print(len(section["SectionData"]))
                
            if tag == b"\x7B\x1D\x92\x6D": # KeyAssetsSection
                entry_count = size // 8 # Each ID is 8 bytes
                
                self.KeyAssetIDs = []
                for j in range(entry_count):
                    self.KeyAssetIDs.append( read_uint64(f, ENDIANNESS) )
            
                f.seek(offset)
                section["SectionData"] = f.read(8 * entry_count)
                print(len(section["SectionData"]))
                
            if tag == b"\xB5\x20\xD7\xDC": # OffsetsSection
                entry_count = size // 8 # 8 Bytes per entry
                
                self.OffsetsMap = []
                for j in range(entry_count):
                    archive_index = read_uint(f, ENDIANNESS)
                    offset_in_archive = read_uint(f, ENDIANNESS)
                    
                    self.OffsetsMap.append( {"ArchiveIndex": archive_index, "OffsetInArchive": offset_in_archive} )
                    
                f.seek(offset)
                print(entry_count)
                section["SectionData"] = f.read(8 * entry_count)
                print(len(section["SectionData"]))
                
            if tag == b"\xA9\xAD\xE8\xED": #SpansSection
                entry_count = size // 8 # 8 Bytes per entry
                
                self.Spans = []
                for j in range(entry_count):
                    asset_index = read_uint(f, ENDIANNESS)
                    count = read_uint(f, ENDIANNESS)
                    
                    self.Spans.append( {"AssetIndex": asset_index, "Count": count} )
        
    
                f.seek(offset)
                section["SectionData"] = f.read(8 * entry_count)
                print(len(section["SectionData"]))
                
                
                
        
        
    

    def WriteDecompressedTOC(self, out):
        out.write(b"1TAD") # DAT1
        out.write(b"\x06\xE0\xB8\x51")
        
        write_uint(out, ENDIANNESS, self.SizeDAT1)
        write_ushort(out, ENDIANNESS, self.SectionsCount) # 6, MSMR
        write_ushort(out, ENDIANNESS, self.UnknownsCount) # 0, MSMR
        
        
  
        for section in self.Sections:
            out.write(section["Tag"])
            write_uint(out, ENDIANNESS, section["Offset"]) # Offset, to be rewritten
            write_uint(out, ENDIANNESS, section["Size"]) # Size, to be rewritten
            
            
        for i in range(self.UnknownsCount):
            write_uint(out, ENDIANNESS, 0)
            
        
        out.write(b"ArchiveTOC") # ArchiveTOC
        
        write_alignment(16, out, out.tell()) # 16-byte alignment bytes written
        
        SectionsNewOffsets = []
        for section in self.Sections:
            SectionsNewOffsets.append(out.tell())
            out.write(section["SectionData"])
            
        for section, new_section_offset in zip(self.Sections, SectionsNewOffsets):
            section["Offset"] = new_section_offset
            section["Size"] = len(section["SectionData"])
            
            
        self.SizeDAT1 = len(out.getvalue())
        
        
        
    def RewriteDecompressedTOC(self, out):
        out.seek(0) # Seek to beginning
        out.truncate() # Clear everything
        self.WriteDecompressedTOC(out) # Rewrite everything
        
        
    def CompressTOC(self):
            self.CompressedTOC = zlib.compress(self.DecompressedTOC, level=9)
            
            
            