

# Packet Deconstruction
Mesages appear to have an 8 byte prelude, then the message which includes a 2 byte CRC and then a line return (CR in this case but it may vary)

`44 4a 00 01 00 08 ff 04  51 50 49 be ac 0d         DJ...... QPI...`


the header itself appears to be comprised of:

`44 4a 00 01 00 08 ff 04`

2 byte counter that increments on each request from the server (the response from the inverter echos the same counter)
`44 4a`


The second set of bytes appears to be constant across sessions and messages
`00 01` 

This appears to scale with the length of the messages, maybe total length including the FF 04 which appears to be constant and not actually part of the message
`00 08`
eg `44 4c 00 01 00 09 ff 04  51 53 49 44 bb 05 0d`  has `00 09` for a message which is 1 byte longer



the last 2 bytes of the header appear to be constant across sessions and query messages, however are different for set commands 
query: `ff 04 `
set: `01 04`

# Set Commands

## Output Priority
### to util-sol-batt
`0000   6a 4c 00 01 00 0a 01 04 50 4f 50 30 30 c2 48 0d   jL......POP00.H.`
### to sol-bat-util
`0000   69 dc 00 01 00 0a 01 04 50 4f 50 30 32 e2 0b 0d   i.......POP02...`
### to sol-util-batt
`0000   69 e0 00 01 00 0a 01 04 50 4f 50 30 31 d2 69 0d   i.......POP01.i.`

## Charging Priority
### to solar first
`0000   6a 67 00 01 00 0a 01 04 50 43 50 30 31 9d 5b 0d   jg......PCP01.[.`
### to solar and utility
`0000   6a 69 00 01 00 0a 01 04 50 43 50 30 32 ad 38 0d   ji......PCP02.8.`
### to only solar charging
`0000   6a 6b 00 01 00 0a 01 04 50 43 50 30 33 bd 19 0d   jk......PCP03...`



