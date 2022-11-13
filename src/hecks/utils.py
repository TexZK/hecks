# Copyright (c) 2021, Andrea Zoppi. All rights reserved.
#
# This file is part of Hecks.
#
# Hecks is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Hecks is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Hecks.  If not, see <https://www.gnu.org/licenses/>.

import base64
import binascii
import enum
import lzma
import re
from ast import literal_eval as _literal_eval
from typing import Iterable
from typing import Iterator
from typing import Mapping
from typing import Sequence
from typing import Tuple

import hexrec.utils
from bytesparse.inplace import Memory

BIN_SET = set('01')
OCT_SET = set('01234567')
DEC_SET = set('0123456789')
HEX_SET = set('0123456789ABCDEFabcdef')

HEX_PREFIX_REGEX = re.compile(r"^(?P<sign>[+-]?)\s*(0[Xx])(?P<body>[0-9A-Fa-f]+(['_][0-9A-Fa-f]+)*)$")
HEX_SUFFIX_REGEX = re.compile(r"^(?P<sign>[+-]?)\s*(0[Xx])?(?P<body>[0-9A-Fa-f]+(['_][0-9A-Fa-f]+)*)[Hh]$")

OCT_PREFIX_REGEX = re.compile(r"^(?P<sign>[+-]?)\s*(0[Oo]?)(?P<body>[0-7]+(['_][0-7]+)*)$")
OCT_SUFFIX_REGEX = re.compile(r"^(?P<sign>[+-]?)\s*(0[Oo]?)?(?P<body>[0-7]+(['_][0-7]+)*)[Oo]$")

BIN_PREFIX_REGEX = re.compile(r"^(?P<sign>[+-]?)\s*(0[Bb])(?P<body>[01]+(['_][01]+)*)$")
BIN_SUFFIX_REGEX = re.compile(r"^(?P<sign>[+-]?)\s*(0[Bb])?(?P<body>[01]+(['_][01]+)*)[Bb]$")

DEC_AFFIX_REGEX = re.compile(r"^(?P<sign>[+-]?)\s*(0[Dd])?(?P<body>[0-9]+(['_][0-9]+)*)[Dd]?$")

_INT_REGEX_DICT = {
    -16: HEX_PREFIX_REGEX,
    +16: HEX_SUFFIX_REGEX,

    -8: OCT_PREFIX_REGEX,
    +8: OCT_SUFFIX_REGEX,

    -2: BIN_PREFIX_REGEX,
    +2: BIN_SUFFIX_REGEX,

    10: DEC_AFFIX_REGEX,
}


def parse_int(
    text: str,
    body_required: bool = True,
) -> Tuple[int, str, int]:

    for base2, regex in _INT_REGEX_DICT.items():
        match = regex.match(text)
        if match:
            base = abs(base2)
            break
    else:
        raise ValueError(f'Invalid integer format: {text}')
    gd = match.groupdict()
    sign = gd['sign']
    body = gd['body'].replace("'", '')
    if not body_required and not body:
        body = '0'
    value = int(body, base)
    return value, sign, base


@enum.unique
class ValueFormatEnum(enum.IntEnum):
    HEXADECIMAL_UPPER = 0
    HEXADECIMAL_LOWER = 1
    DECIMAL = 2
    OCTAL = 3
    BINARY = 4


VALUE_FORMAT_INTEGER_BASE: Mapping[ValueFormatEnum, int] = {
    ValueFormatEnum.HEXADECIMAL_UPPER: 16,
    ValueFormatEnum.HEXADECIMAL_LOWER: 16,
    ValueFormatEnum.DECIMAL:           10,
    ValueFormatEnum.OCTAL:             8,
    ValueFormatEnum.BINARY:            2,
}

VALUE_FORMAT_CHAR: Mapping[ValueFormatEnum, str] = {
    ValueFormatEnum.HEXADECIMAL_UPPER: 'X',
    ValueFormatEnum.HEXADECIMAL_LOWER: 'x',
    ValueFormatEnum.DECIMAL:           'd',
    ValueFormatEnum.OCTAL:             'o',
    ValueFormatEnum.BINARY:            'b',
}

VALUE_FORMAT_PREFIX: Mapping[ValueFormatEnum, str] = {
    ValueFormatEnum.HEXADECIMAL_UPPER: '0x',
    ValueFormatEnum.HEXADECIMAL_LOWER: '0x',
    ValueFormatEnum.DECIMAL:           '',
    ValueFormatEnum.OCTAL:             '0',
    ValueFormatEnum.BINARY:            '0b',
}

VALUE_FORMAT_SUFFIX: Mapping[ValueFormatEnum, str] = {
    ValueFormatEnum.HEXADECIMAL_UPPER: 'h',
    ValueFormatEnum.HEXADECIMAL_LOWER: 'h',
    ValueFormatEnum.DECIMAL:           'd',
    ValueFormatEnum.OCTAL:             'o',
    ValueFormatEnum.BINARY:            'b',
}


def format_uint(
    value: int,
    base: ValueFormatEnum = ValueFormatEnum.DECIMAL,
    prefix: bool = False,
    suffix: bool = False,
    zeros: bool = False,
    bytesize: int = 4,
) -> str:

    if value < 0:
        raise ValueError('not unsigned')

    c = VALUE_FORMAT_CHAR[base]
    p = VALUE_FORMAT_PREFIX[base] if prefix else ''
    s = VALUE_FORMAT_SUFFIX[base] if suffix else ''

    if zeros:
        if bytesize <= 0:
            raise ValueError('bytesize must be positive')
        bitsize = 8 * bytesize
        maxi = (1 << bitsize) - 1

        fmt = f"{{:{c}}}"
        n = len(fmt.format(maxi))
        z = f'0{n}' if zeros else ''
    else:
        z = ''

    fmt = f'{p}{{:{z}{c}}}{s}'
    text = fmt.format(value)
    return text


def chop(
    vector: Sequence[int],
    window: int,
    align_base: int = 0,
) -> Iterator[int]:

    window = int(window)
    if window <= 0:
        raise ValueError('non-positive window')

    align_base = int(align_base)
    if align_base:
        offset = -align_base % window
        chunk = vector[:offset]
        yield chunk
    else:
        offset = 0

    for i in range(offset, len(vector), window):
        yield vector[i:(i + window)]


MIME_TYPE: str = 'application/hecks'


CLIPBOARD_ENCODERS = {
    'repr': repr,
    'hex-lo': binascii.hexlify,
    'hex-up': lambda data: binascii.hexlify(data).upper(),
    'hex-lo-dot': lambda data: b'.'.join(hexrec.utils.chop(binascii.hexlify(data), 2)),
    'hex-up-dot': lambda data: b'.'.join(hexrec.utils.chop(binascii.hexlify(data).upper(), 2)),
    'base64': base64.b64encode,
    'base85': base64.b85encode,
}

CLIPBOARD_DECODERS = {
    'repr': _literal_eval,
    'hex-lo': binascii.unhexlify,
    'hex-up': binascii.unhexlify,
    'hex-lo-dot': lambda ascii: binascii.unhexlify(ascii.replace(b'.', b'')),
    'hex-up-dot': lambda ascii: binascii.unhexlify(ascii.replace(b'.', b'')),
    'base64': base64.b64decode,
    'base85': base64.b85decode,
}


CLIPBOARD_COMPRESSORS = {
    'none': lambda x: x,
    'lzma': lzma.compress,
}

CLIPBOARD_DECOMPRESSORS = {
    'none': lambda x: x,
    'lzma': lzma.decompress,
}


def memory_to_clipboard(
    memory: Memory,
    encoding: str = 'hex-up-dot',
    compression: str = 'none',
    base: ValueFormatEnum = ValueFormatEnum.HEXADECIMAL_UPPER,
    prefix: bool = False,
) -> str:

    def format_address(value: int) -> str:
        return format_uint(value, base, prefix, not prefix)

    encoding = str(encoding)
    encoder = CLIPBOARD_ENCODERS[encoding]

    compression = str(compression)
    compressor = CLIPBOARD_COMPRESSORS[compression]

    count = 0
    block_tokens = []

    for address, items in memory.blocks():
        count += 1
        size = len(items)

        block_tokens += [
            f'Address: {format_address(address)}',
            f'Size: {format_address(size)}',
            encoder(compressor(items)).decode('ascii'),
            '',
        ]
        del items  # discard

    header_tokens = [
        'MIME-Version: 1.0',
        f'Content-Type: {MIME_TYPE}',
        f'Data-Encoding: {encoding}',
        f'Data-Compression: {compression}',
        f'Block-Count: {count}',
        f'Address-Start: {format_address(memory.start)}',
        f'Address-End-Ex: {format_address(memory.endex)}',
        ''
    ]

    clipboard = '\n'.join(header_tokens + block_tokens)
    return clipboard


def iter_lines(text: str) -> Iterator[str]:
    start = 0
    while 1:
        endex = text.find('\n', start)
        if endex < 0:
            endex = len(text)
        yield text[start:endex]
        start = endex + 1


def clipboard_to_memory(
    clipboard: Iterable[str],
) -> Memory:

    it = iter(clipboard)

    # Parse header
    header = {}
    while 1:
        line = next(it)
        if not line:
            break
        split = line.index(':')
        key = line[:split].strip()
        value = line[split + 1:].strip()
        header[key] = value

    key = 'MIME-Version'
    value = header.get(key)
    if value != '1.0':
        raise ValueError(f'Unsupported {key}: {value}')

    key = 'Data-Encoding'
    value = header.get(key)
    if value not in CLIPBOARD_DECODERS:
        raise ValueError(f'Unsupported {key}: {value}')
    decoder = CLIPBOARD_DECODERS[value]

    key = 'Data-Compression'
    value = header.get(key)
    if value not in CLIPBOARD_DECOMPRESSORS:
        raise ValueError(f'Unsupported {key}: {value}')
    decompressor = CLIPBOARD_DECOMPRESSORS[value]

    key = 'Block-Count'
    value = header.get(key)
    if not value:
        raise ValueError(f'Missing {key}')
    count = parse_int(value)[0]
    if count < 0:
        raise ValueError(f'Negative {key}')

    key = 'Address-Start'
    value = header.get(key)
    if not value:
        raise ValueError(f'Missing {key}')
    start = parse_int(value)[0]

    key = 'Address-End-Ex'
    value = header.get(key)
    if not value:
        raise ValueError(f'Missing {key}')
    endex = parse_int(value)[0]

    if endex < start:
        raise ValueError(f'Negative address range')
    memory = Memory(start=start, endex=endex)

    for _ in range(count):
        line = next(it)
        split = line.index(':')
        key = line[:split].strip()
        value = line[split + 1:].strip()
        if key != 'Address':
            raise ValueError(f'Expecting Address, got: {key}')
        if value.endswith('h'):
            address = int(value[:-1], 16)
        else:
            address = int(value)

        line = next(it)
        split = line.index(':')
        key = line[:split].strip()
        value = line[split + 1:].strip()
        if key != 'Size':
            raise ValueError(f'Expecting Size, got {key}')
        if value.endswith('h'):
            size = int(value[:-1], 16)
        else:
            size = int(value)

        line = next(it)
        while line:
            data = decompressor(decoder(line.encode('ascii')))
            if len(data) < size:
                raise ValueError(f'Expecting {size} bytes, got {len(data)}')
            elif len(data) > size:
                data = data[:size]
            memory.write(address, data)
            del data
            line = next(it)

    return memory
