"""Minimal PNG read/write for RGBA images, standard library only.

Supports exactly what the fixtures need: 8-bit RGBA (colour type 6),
tEXt chunks, and all five PNG row filters on decode (None, Sub, Up,
Average, Paeth). Encoding can write rows with the None or Sub filter;
the re-encode fixture step uses Sub so its bytes differ from the
original while its pixels are identical.
"""

import struct
import zlib

_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_BPP = 4  # bytes per pixel, RGBA


def _chunk(kind, data):
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def _filter_row(kind, row, prev):
    if kind == 0:
        return bytes(row)
    if kind == 1:  # Sub
        out = bytearray(len(row))
        for i, value in enumerate(row):
            left = row[i - _BPP] if i >= _BPP else 0
            out[i] = (value - left) & 0xFF
        return bytes(out)
    raise ValueError("encoder only writes filter 0 or 1, got %r" % kind)


def _unfilter_row(kind, row, prev):
    out = bytearray(len(row))
    if kind == 0:
        out[:] = row
    elif kind == 1:  # Sub
        for i, value in enumerate(row):
            left = out[i - _BPP] if i >= _BPP else 0
            out[i] = (value + left) & 0xFF
    elif kind == 2:  # Up
        for i, value in enumerate(row):
            out[i] = (value + prev[i]) & 0xFF
    elif kind == 3:  # Average
        for i, value in enumerate(row):
            left = out[i - _BPP] if i >= _BPP else 0
            out[i] = (value + ((left + prev[i]) >> 1)) & 0xFF
    elif kind == 4:  # Paeth
        for i, value in enumerate(row):
            a = out[i - _BPP] if i >= _BPP else 0
            b = prev[i]
            c = prev[i - _BPP] if i >= _BPP else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            predictor = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            out[i] = (value + predictor) & 0xFF
    else:
        raise ValueError("unknown PNG filter %r" % kind)
    return bytes(out)


def encode_png(width, height, pixels, text_chunks=(), row_filter=0):
    """Encode RGBA pixels (row-major, no filter bytes) as a PNG.

    text_chunks is an iterable of (keyword, text) pairs written as tEXt
    chunks before IDAT. Deterministic for fixed inputs.
    """
    if len(pixels) != width * height * _BPP:
        raise ValueError("pixel buffer size does not match dimensions")
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = bytearray()
    stride = width * _BPP
    prev = bytes(stride)
    for y in range(height):
        row = pixels[y * stride:(y + 1) * stride]
        raw.append(row_filter)
        raw.extend(_filter_row(row_filter, row, prev))
        prev = row
    parts = [_SIGNATURE, _chunk(b"IHDR", ihdr)]
    for keyword, text in text_chunks:
        parts.append(
            _chunk(b"tEXt", keyword.encode("latin-1") + b"\x00" + text.encode("latin-1"))
        )
    parts.append(_chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
    parts.append(_chunk(b"IEND", b""))
    return b"".join(parts)


def _iter_chunks(data):
    if not data.startswith(_SIGNATURE):
        raise ValueError("not a PNG file")
    pos = len(_SIGNATURE)
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        yield kind, payload
        pos += 12 + length


def decode_png(data):
    """Return (width, height, pixels, text) for an 8-bit RGBA PNG.

    pixels are the decoded RGBA bytes (filters removed). text maps tEXt
    keywords to their text values.
    """
    width = height = None
    idat = bytearray()
    text = {}
    for kind, payload in _iter_chunks(data):
        if kind == b"IHDR":
            width, height, depth, colour, _comp, _filt, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if depth != 8 or colour != 6 or interlace != 0:
                raise ValueError("only non-interlaced 8-bit RGBA PNGs are supported")
        elif kind == b"tEXt":
            keyword, _nul, value = payload.partition(b"\x00")
            text[keyword.decode("latin-1")] = value.decode("latin-1")
        elif kind == b"IDAT":
            idat.extend(payload)
    if width is None:
        raise ValueError("PNG has no IHDR")
    raw = zlib.decompress(bytes(idat))
    stride = width * _BPP
    pixels = bytearray()
    prev = bytes(stride)
    pos = 0
    for _y in range(height):
        kind = raw[pos]
        row = _unfilter_row(kind, raw[pos + 1:pos + 1 + stride], prev)
        pixels.extend(row)
        prev = row
        pos += 1 + stride
    return width, height, bytes(pixels), text


def strip_text_chunks(data):
    """Return the PNG with every tEXt chunk removed; pixels untouched."""
    parts = [_SIGNATURE]
    for kind, payload in _iter_chunks(data):
        if kind == b"tEXt":
            continue
        parts.append(_chunk(kind, payload))
    return b"".join(parts)


def resize_nearest(width, height, pixels, new_width, new_height):
    """Nearest-neighbour resize of an RGBA pixel buffer (deterministic)."""
    out = bytearray(new_width * new_height * _BPP)
    for y in range(new_height):
        src_y = (y * height) // new_height
        for x in range(new_width):
            src_x = (x * width) // new_width
            src = (src_y * width + src_x) * _BPP
            dst = (y * new_width + x) * _BPP
            out[dst:dst + _BPP] = pixels[src:src + _BPP]
    return bytes(out)


def crop_pixels(width, height, pixels, box):
    """Crop to box = (left, upper, right, lower); return (w, h, pixels)."""
    left, upper, right, lower = box
    new_width, new_height = right - left, lower - upper
    out = bytearray()
    stride = width * _BPP
    for y in range(upper, lower):
        start = y * stride + left * _BPP
        out.extend(pixels[start:start + new_width * _BPP])
    return new_width, new_height, bytes(out)
