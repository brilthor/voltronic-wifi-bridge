#!/bin/python

def cal_crc_half(message, length=None, string_is_hex=False):
    # translated to python from inverter.cpp from 
    crc_ta= [
        0x0000,0x1021,0x2042,0x3063,0x4084,0x50a5,0x60c6,0x70e7,
        0x8108,0x9129,0xa14a,0xb16b,0xc18c,0xd1ad,0xe1ce,0xf1ef
    ]

    crc = 0

    for b in bytearray(message):
        # highest 4 bits of CRC
        da = crc.to_bytes(2)[0] >> 4
        crc = crc << 4
        crc = crc ^ crc_ta[da^(b>>4)]

        crc = crc & 0xFFFF
        da = crc.to_bytes(2)[0] >> 4
        crc = crc << 4
        crc = crc  ^ crc_ta[da^(b & 0x0f)]

        # cut off anything about the two bytes
        crc = crc & 0xFFFF

    # aviod special characters in the protocol (, CR, LF
    # I'm sure this could be cleaner
    crcbytes = crc.to_bytes(2)
    for index in [0,1]:
        if crcbytes[index] in [0x28, 0x0d, 0x0a]:
            crc += (0x100 ** index)
    crcbytes = crc.to_bytes(2)
    return crcbytes
