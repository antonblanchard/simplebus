from enum import IntEnum, unique

@unique
class CmdEnum(IntEnum):
    READ = 0x2
    WRITE = 0x3
    READ_ACK = 0x82
    WRITE_ACK = 0x83
