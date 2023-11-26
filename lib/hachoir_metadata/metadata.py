# -*- coding: utf-8 -*-
from lib.hachoir_core.compatibility import any, sorted
from lib.hachoir_core.endian import endian_name
from lib.hachoir_core.tools import makePrintable, makeUnicode
from lib.hachoir_core.dict import Dict
from lib.hachoir_core.error import error, HACHOIR_ERRORS
from lib.hachoir_core.i18n import _
from lib.hachoir_core.log import Logger
from lib.hachoir_metadata.metadata_item import (
    MIN_PRIORITY, MAX_PRIORITY, QUALITY_NORMAL)
from lib.hachoir_metadata.register import registerAllItems

extractors = {}

class Metadata(Logger):
    header = u"Metadata"

    def __init__(self, parent, quality=QUALITY_NORMAL):
        assert isinstance(self.header, unicode)

        # Limit to 0.0 .. 1.0
        quality = parent.quality if parent else min(max(0.0, quality), 1.0)
        object.__init__(self)
        object.__setattr__(self, "_Metadata__data", {})
        object.__setattr__(self, "quality", quality)
        header = self.__class__.header
        object.__setattr__(self, "_Metadata__header", header)

        registerAllItems(self)

    def _logger(self):
        pass

    def __setattr__(self, key, value):
        """
        Add a new value to data with name 'key'. Skip duplicates.
        """
        # Invalid key?
        if key not in self.__data:
            raise KeyError(_("%s has no metadata '%s'") % (self.__class__.__name__, key))

        # Skip duplicates
        self.__data[key].add(value)

    def setHeader(self, text):
        object.__setattr__(self, "header", text)

    def getItems(self, key):
        try:
            return self.__data[key]
        except LookupError:
            raise ValueError(f"Metadata has no value '{key}'")

    def getItem(self, key, index):
        try:
            return self.getItems(key)[index]
        except (LookupError, ValueError):
            return None

    def has(self, key):
        return len(self.getItems(key)) >= 1

    def get(self, key, default=None, index=0):
        """
        Read first value of tag with name 'key'.

        >>> from datetime import timedelta
        >>> a = RootMetadata()
        >>> a.duration = timedelta(seconds=2300)
        >>> a.get('duration')
        datetime.timedelta(0, 2300)
        >>> a.get('author', u'Anonymous')
        u'Anonymous'
        """
        item = self.getItem(key, index)
        if item is None:
            if default is None:
                raise ValueError(f"Metadata has no value '{key}' (index {index})")
            else:
                return default
        return item.value

    def getValues(self, key):
        try:
            data = self.__data[key]
        except LookupError:
            raise ValueError(f"Metadata has no value '{key}'")
        return [ item.value for item in data ]

    def getText(self, key, default=None, index=0):
        """
        Read first value, as unicode string, of tag with name 'key'.

        >>> from datetime import timedelta
        >>> a = RootMetadata()
        >>> a.duration = timedelta(seconds=2300)
        >>> a.getText('duration')
        u'38 min 20 sec'
        >>> a.getText('titre', u'Unknown')
        u'Unknown'
        """
        item = self.getItem(key, index)
        return item.text if item is not None else default

    def register(self, data):
        assert data.key not in self.__data
        data.metadata = self
        self.__data[data.key] = data

    def __iter__(self):
        return self.__data.itervalues()

    def __str__(self):
        r"""
        Create a multi-line ASCII string (end of line is "\n") which
        represents all datas.

        >>> a = RootMetadata()
        >>> a.author = "haypo"
        >>> a.copyright = unicode("© Hachoir", "UTF-8")
        >>> print a
        Metadata:
        - Author: haypo
        - Copyright: \xa9 Hachoir

        @see __unicode__() and exportPlaintext()
        """
        text = self.exportPlaintext()
        return "\n".join( makePrintable(line, "ASCII") for line in text )

    def __unicode__(self):
        r"""
        Create a multi-line Unicode string (end of line is "\n") which
        represents all datas.

        >>> a = RootMetadata()
        >>> a.copyright = unicode("© Hachoir", "UTF-8")
        >>> print repr(unicode(a))
        u'Metadata:\n- Copyright: \xa9 Hachoir'

        @see __str__() and exportPlaintext()
        """
        return "\n".join(self.exportPlaintext())

    def exportPlaintext(self, priority=None, human=True, line_prefix=u"- ", title=None):
        r"""
        Convert metadata to multi-line Unicode string and skip datas
        with priority lower than specified priority.

        Default priority is Metadata.MAX_PRIORITY. If human flag is True, data
        key are translated to better human name (eg. "bit_rate" becomes
        "Bit rate") which may be translated using gettext.

        If priority is too small, metadata are empty and so None is returned.

        >>> print RootMetadata().exportPlaintext()
        None
        >>> meta = RootMetadata()
        >>> meta.copyright = unicode("© Hachoir", "UTF-8")
        >>> print repr(meta.exportPlaintext())
        [u'Metadata:', u'- Copyright: \xa9 Hachoir']

        @see __str__() and __unicode__()
        """
        if priority is not None:
            priority = max(priority, MIN_PRIORITY)
            priority = min(priority, MAX_PRIORITY)
        else:
            priority = MAX_PRIORITY
        if not title:
            title = self.header
        text = [f"{title}:"]
        for data in sorted(self):
            if priority < data.priority:
                break
            if not data.values:
                continue
            title = data.description if human else data.key
            for item in data.values:
                value = item.text if human else makeUnicode(item.value)
                text.append(f"{line_prefix}{title}: {value}")
        return text if len(text) > 1 else None

    def __nonzero__(self):
        return any(self.__data.itervalues())

class RootMetadata(Metadata):
    def __init__(self, quality=QUALITY_NORMAL):
        Metadata.__init__(self, None, quality)

class MultipleMetadata(RootMetadata):
    header = _("Common")
    def __init__(self, quality=QUALITY_NORMAL):
        RootMetadata.__init__(self, quality)
        object.__setattr__(self, "_MultipleMetadata__groups", Dict())
        object.__setattr__(self, "_MultipleMetadata__key_counter", {})

    def __contains__(self, key):
        return key in self.__groups

    def __getitem__(self, key):
        return self.__groups[key]

    def iterGroups(self):
        return self.__groups.itervalues()

    def __nonzero__(self):
        if RootMetadata.__nonzero__(self):
            return True
        return any(bool(group) for group in self.__groups)

    def addGroup(self, key, metadata, header=None):
        """
        Add a new group (metadata of a sub-document).

        Returns False if the group is skipped, True if it has been added.
        """
        if not metadata:
            self.warning(f"Skip empty group {key}")
            return False
        if key.endswith("[]"):
            key = key[:-2]
            if key in self.__key_counter:
                self.__key_counter[key] += 1
            else:
                self.__key_counter[key] = 1
            key += "[%u]" % self.__key_counter[key]
        if header:
            metadata.setHeader(header)
        self.__groups.append(key, metadata)
        return True

    def exportPlaintext(self, priority=None, human=True, line_prefix=u"- "):
        if common := Metadata.exportPlaintext(self, priority, human, line_prefix):
            text = common
        else:
            text = []
        for key, metadata in self.__groups.iteritems():
            title = key if not human else None
            if value := metadata.exportPlaintext(
                priority, human, line_prefix, title=title
            ):
                text.extend(value)
        return text if len(text) else None

def registerExtractor(parser, extractor):
    assert parser not in extractors
    assert issubclass(extractor, RootMetadata)
    extractors[parser] = extractor

def extractMetadata(parser, quality=QUALITY_NORMAL):
    """
    Create a Metadata class from a parser. Returns None if no metadata
    extractor does exist for the parser class.
    """
    try:
        extractor = extractors[parser.__class__]
    except KeyError:
        return None
    metadata = extractor(quality)
    try:
        metadata.extract(parser)
    except HACHOIR_ERRORS, err:
        error("Error during metadata extraction: %s" % unicode(err))
    if metadata:
        metadata.mime_type = parser.mime_type
        metadata.endian = endian_name[parser.endian]
    return metadata

