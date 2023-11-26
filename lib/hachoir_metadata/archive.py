from lib.hachoir_metadata.metadata_item import QUALITY_BEST, QUALITY_FASTEST
from lib.hachoir_metadata.safe import fault_tolerant, getValue
from lib.hachoir_metadata.metadata import (
    RootMetadata, Metadata, MultipleMetadata, registerExtractor)
from lib.hachoir_parser.archive import (Bzip2Parser, CabFile, GzipParser,
    TarFile, ZipFile, MarFile)
from lib.hachoir_core.tools import humanUnixAttributes
from lib.hachoir_core.i18n import _

def maxNbFile(meta):
    if meta.quality <= QUALITY_FASTEST:
        return 0
    return None if QUALITY_BEST <= meta.quality else 1 + int(10 * meta.quality)

def computeCompressionRate(meta):
    """
    Compute compression rate, sizes have to be in byte.
    """
    if not meta.has("file_size") \
    or not meta.get("compr_size", 0):
        return
    if file_size := meta.get("file_size"):
        meta.compr_rate = float(file_size) / meta.get("compr_size")
    else:
        return

class Bzip2Metadata(RootMetadata):
    def extract(self, zip):
        if "file" in zip:
            self.compr_size = zip["file"].size/8

class GzipMetadata(RootMetadata):
    def extract(self, gzip):
        self.useHeader(gzip)
        computeCompressionRate(self)

    @fault_tolerant
    def useHeader(self, gzip):
        self.compression = gzip["compression"].display
        if gzip["mtime"]:
            self.last_modification = gzip["mtime"].value
        self.os = gzip["os"].display
        if gzip["has_filename"].value:
            self.filename = getValue(gzip, "filename")
        if gzip["has_comment"].value:
            self.comment = getValue(gzip, "comment")
        self.compr_size = gzip["file"].size/8
        self.file_size = gzip["size"].value

class ZipMetadata(MultipleMetadata):
    def extract(self, zip):
        max_nb = maxNbFile(self)
        for index, field in enumerate(zip.array("file")):
            if max_nb is not None and max_nb <= index:
                self.warning(
                    f"ZIP archive contains many files, but only first {max_nb} files are processed"
                )
                break
            self.processFile(field)

    @fault_tolerant
    def processFile(self, field):
        meta = Metadata(self)
        meta.filename = field["filename"].value
        meta.creation_date = field["last_mod"].value
        meta.compression = field["compression"].display
        if "data_desc" in field:
            meta.file_size = field["data_desc/file_uncompressed_size"].value
            if field["data_desc/file_compressed_size"].value:
                meta.compr_size = field["data_desc/file_compressed_size"].value
        else:
            meta.file_size = field["uncompressed_size"].value
            if field["compressed_size"].value:
                meta.compr_size = field["compressed_size"].value
        computeCompressionRate(meta)
        self.addGroup(field.name, meta, "File \"%s\"" % meta.get('filename'))

class TarMetadata(MultipleMetadata):
    def extract(self, tar):
        max_nb = maxNbFile(self)
        for index, field in enumerate(tar.array("file")):
            if max_nb is not None and max_nb <= index:
                self.warning(
                    f"TAR archive contains many files, but only first {max_nb} files are processed"
                )
                break
            meta = Metadata(self)
            self.extractFile(field, meta)
            if meta.has("filename"):
                title = _('File "%s"') % meta.getText('filename')
            else:
                title = _("File")
            self.addGroup(field.name, meta, title)

    @fault_tolerant
    def extractFile(self, field, meta):
        meta.filename = field["name"].value
        meta.file_attr = humanUnixAttributes(field.getOctal("mode"))
        meta.file_size = field.getOctal("size")
        try:
            if field.getOctal("mtime"):
                meta.last_modification = field.getDatetime()
        except ValueError:
            pass
        meta.file_type = field["type"].display
        meta.author = f'{field["uname"].value} (uid={field.getOctal("uid")}), group {field["gname"].value} (gid={field.getOctal("gid")})'


class CabMetadata(MultipleMetadata):
    def extract(self, cab):
        if "folder[0]" in cab:
            self.useFolder(cab["folder[0]"])
        self.format_version = f'Microsoft Cabinet version {cab["cab_version"].display}'
        self.comment = (
            f'{cab["nb_folder"].value} folders, {cab["nb_files"].value} files'
        )
        max_nb = maxNbFile(self)
        for index, field in enumerate(cab.array("file")):
            if max_nb is not None and max_nb <= index:
                self.warning(
                    f"CAB archive contains many files, but only first {max_nb} files are processed"
                )
                break
            self.useFile(field)

    @fault_tolerant
    def useFolder(self, folder):
        compr = folder["compr_method"].display
        if folder["compr_method"].value != 0:
            compr += " (level %u)" % folder["compr_level"].value
        self.compression = compr

    @fault_tolerant
    def useFile(self, field):
        meta = Metadata(self)
        meta.filename = field["filename"].value
        meta.file_size = field["filesize"].value
        meta.creation_date = field["timestamp"].value
        attr = field["attributes"].value
        if attr != "(none)":
            meta.file_attr = attr
        if meta.has("filename"):
            title = _("File \"%s\"") % meta.getText('filename')
        else:
            title = _("File")
        self.addGroup(field.name, meta, title)

class MarMetadata(MultipleMetadata):
    def extract(self, mar):
        self.comment = f'Contains {mar["nb_file"].value} files'
        self.format_version = f'Microsoft Archive version {mar["version"].value}'
        max_nb = maxNbFile(self)
        for index, field in enumerate(mar.array("file")):
            if max_nb is not None and max_nb <= index:
                self.warning(
                    f"MAR archive contains many files, but only first {max_nb} files are processed"
                )
                break
            meta = Metadata(self)
            meta.filename = field["filename"].value
            meta.compression = "None"
            meta.file_size = field["filesize"].value
            self.addGroup(field.name, meta, "File \"%s\"" % meta.getText('filename'))

registerExtractor(CabFile, CabMetadata)
registerExtractor(GzipParser, GzipMetadata)
registerExtractor(Bzip2Parser, Bzip2Metadata)
registerExtractor(TarFile, TarMetadata)
registerExtractor(ZipFile, ZipMetadata)
registerExtractor(MarFile, MarMetadata)

