from helpers import *
import lz4.block

ENDIANNESS = "<" # Little


class DSAR():
    def ReadDSARHeader(self, f):
        self.Magic = f.read(4) # DSAR
        self.Version = read_uint(f, ENDIANNESS)
        self.BlockCount = read_uint(f, ENDIANNESS)
        self.BlockTableEnd = read_uint(f, ENDIANNESS) # 32 + self.BlockCount * 32
        self.OriginalSize = read_uint64(f, ENDIANNESS)
        self.Padding = f.read(8) # PADDING*
        
    
    
    def ReadBlockTable(self, f):
        self.BlocksHeaders = []
        
        for i in range(self.BlockCount):
            real_offset = read_uint(f, ENDIANNESS)
            f.seek(4, 1) # unk
            
            compressed_offset = read_uint(f, ENDIANNESS)
            f.seek(4, 1) # unk
            
            real_size = read_uint(f, ENDIANNESS)
            compressed_size = read_uint(f, ENDIANNESS)
            
            compression_type = read_uint8(f, ENDIANNESS)
            f.seek(7, 1) # unk, same and repeated every block entry in the table
            
            
            self.BlocksHeaders.append( {"RealOffset": real_offset, "CompressedOffset": compressed_offset, "RealSize": real_size, "CompressedSize": compressed_size, "CompressionType": compression_type} )
            
            
       
       
    def ReadBlock(self, f, block_header):
        f.seek(block_header["CompressedOffset"])
        
        compressed_block = f.read(block_header["CompressedSize"])
        
        if block_header["CompressionType"] == 3:
            decompressed_block = lz4.block.decompress(compressed_block, uncompressed_size=block_header["RealSize"])
            
            return decompressed_block
            
        elif block_header["CompressionType"] == 2:
            raise Exception("Unsupported Compression Type: GDeflate")
            
        else:
            raise Exception(
                f"Unknown Compression Type: {block_header['CompressionType']}"
            )
                
                
            
                
                
    
    def GetAsset(self, f, asset_offset, asset_size, IsDSAR):
        asset_end = asset_offset + asset_size
        
        asset = bytearray()
        
        if not IsDSAR: # Not compressed stream
            f.seek(0)
            uncompressed_stream = f.read()
            asset.extend(uncompressed_stream[asset_offset: asset_end])
        
            return bytes(asset)
            
            
        else: # Compressed DSAR Archive
            for block_header in self.BlocksHeaders:
                block_start = block_header["RealOffset"]
                block_end = block_start + block_header["RealSize"]
                
                if block_start < asset_end and block_end > asset_offset: # Check if part or all of this asset is contained inside this block
                    decompressed_block = self.ReadBlock(f, block_header)
                    
                    asset_start_in_block = max(asset_offset, block_start) - block_start
                    
                    asset_end_in_block = min(asset_end, block_end) - block_start
                                
                    
                    asset.extend(decompressed_block[asset_start_in_block: asset_end_in_block])
                    
            
            
                
            return bytes(asset)