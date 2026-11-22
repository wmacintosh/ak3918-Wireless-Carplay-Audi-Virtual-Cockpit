wademacintosh\@Wades-MacBook-Air AK3918_GitHub % cd "$HOME/AK3918_GitHub"

git pull --ff-only

set -o pipefail



bash scripts/step142_isolated_elf_audit.sh

remote: Enumerating objects: 41, done.

remote: Counting objects: 100% (41/41), done.

remote: Compressing objects: 100% (32/32), done.

remote: Total 33 (delta 19), reused 0 (delta 0), pack-reused 0 (from 0)

Unpacking objects: 100% (33/33), 14.99 KiB | 189.00 KiB/s, done.

From https\://github.com/wmacintosh/ak3918-Wireless-Carplay-Audi-Virtual-Cockpit

   3273d00..caa275f  wip/ak3918-step115-callback-tombstones -> origin/wip/ak3918-step115-callback-tombstones

Updating 3273d00..caa275f

Fast-forward

 .github/workflows/experimental-source-checks.yml |   5 ++

 docs/STEP141_EXPERIMENTAL_PRE_FLASH_GATE.md      |  21 ++++++

 docs/STEP142_ISOLATED_PATCHED_ELF_AUDIT.md       |  59 ++++++++++++++++

 scripts/step142_audit_patched_elf.py             | 248 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

 scripts/step142_isolated_elf_audit.sh            | 144 +++++++++++++++++++++++++++++++++++++++

 tests/test_step142_isolated_elf_audit.py         | 122 +++++++++++++++++++++++++++++++++

 6 files changed, 599 insertions(+)

 create mode 100644 docs/STEP142_ISOLATED_PATCHED_ELF_AUDIT.md

 create mode 100644 scripts/step142_audit_patched_elf.py

 create mode 100644 scripts/step142_isolated_elf_audit.sh

 create mode 100644 tests/test_step142_isolated_elf_audit.py

STEP 142 ISOLATED ARM ELF BUILD AND STATIC AUDIT

This process NEVER packages or flashes firmware.

The repo and Buildroot toolchain are mounted read-only.

The Docker container has --network none and does not keep any compiled image.

MAC_REPOSITORY=/Users/wademacintosh/AK3918_GitHub



\===== REPEAT VERIFIED-STOCK STEP 141 INPUT PREFLIGHT =====

STEP 141 OFFLINE READ-ONLY EXPERIMENTAL PREFLIGHT

This script does NOT build, package, upload or flash firmware.

PASS: isolated WIP branch, clean tracked tree, commit caa275f32452

PASS: combined=1 phone=1, opt-in test-only package plan

PASS: exact original ARM stock SHA256 and patch-input invariants

PASS: in-memory mapped zero-gap candidate VA=0x102e74 file=0xf2e74 bytes=30

PASS: in-memory mapped zero-gap candidate VA=0x102e94 file=0xf2e94 bytes=12

PASS: in-memory mapped zero-gap candidate VA=0x102ea0 file=0xf2ea0 bytes=12

PASS: in-memory mapped zero-gap candidate VA=0x102eac file=0xf2eac bytes=12

PASS: historical recovery archive hash, file names and member safety

PASS: all five builder inputs equal original recovery archive members

PASS: historical installer is for stock/legacy tar ONLY, not this experiment

INFO: AK_UCLIBC_CC unset on host; builder requires ARM/uClibc compiler

PASS: STEP141 OFFLINE STATIC PREFLIGHT

BLOCKED FOR FLASH: preflight does not validate a final built/repaired ELF, ARM imports in the target loader, independent recovery if CGI is unavailable, or actual car runtime.

/usr/bin/python3

/usr/bin/readelf



\===== BUILD ARM/uClibc 111+PHONE SHIM AND PATCH COPIED STOCK ELF =====

PASS: builder package_plan() is None; no tar generation

PASS: ELF32 ARM, soft float, uClibc dependency, constructor, exported hook

patched @0x3b43c 0x0a000002->0xea000002 (nostrip: keep all displays in /info)

patched @0x3c2e0 0x1a000009->0xea000009 (enabledFeatures: always create array)

patched @0x3c364 0x0a000012->0xe1a00000 (enabledFeatures: always append viewAreas)

patched @0x3c3c4 0x0a000005->0xe1a00000 (enabledFeatures: always take cornerMasks slot)

patched @0x3c678 0x000bbfc6->0x000b6d95 (cornerMasks slot -> altScreen CFL (0xf34ea))

initialized hook slot @0x1369fc (file 0x1169fc) = 0x6a60c

wrote ARM trampoline @0x102e74 (file 0xf2e74)

patched Setup BL @0x5ec50: 0xeb002e6d -> 0xeb029087 (trampoline 0x102e74)

strings @0x102e80 NEEDED off=0xef17c RUNPATH off=0xef186

injected DT_NEEDED + DT_RUNPATH into slots 33,34

reserved 12 bytes of hook pointer slots from 0x13c640

patched finalizer callback 0x134078: 0x66a40 -> 0x102e94

EXPERIMENTAL combined stream construction: 0x2fadc -> 0x102ea0; ptr 0x13c644

EXPERIMENTAL combined screen HTTP send: 0x2fbb0 -> 0x102eac; ptr 0x13c648

sdDongle md5 bf66fb161209ad484324a015e308847b

REPAIR RESULT: {'new_dynstr_va': '0x123434', 'new_dynstr_size': 12124, 'file_size': 1223820}

PASS: compiled and repaired ephemeral copies only



\===== STATIC AUDIT OF ACTUAL REPAIRED ELF AND LIBRARY =====

PASS: session setup: original 0x5ec50 -> trampoline 0x102e74 -> pointer slot 0x1369fc

PASS: stream-array ensure: original 0x2fadc -> trampoline 0x102ea0 -> pointer slot 0x13c644

PASS: HTTP screen send: original 0x2fbb0 -> trampoline 0x102eac -> pointer slot 0x13c648

PASS: class finalizer slot 0x134078 -> trampoline 0x102e94 -> 0x13c640

PASS: original five display patches match expected ARM words

PASS: BSS size increased by precisely three 32-bit callback slots

PASS: relocated DT_STRTAB, DT_NEEDED [b'libSdCommon.so', b'libstdc++.so.6', b'libdns_sd.so', b'libSdUtils.so', b'libfdk-aac.so.2', b'libopus.so.0', b'libasound.so.2', b'libusb-1.0.so.0', b'libexecinfo.so', b'libgcc_s.so.1', b'libc.so.0', b'libSdH.so'] and RUNPATH=$ORIGIN

PASS: both file-backed PT_LOAD ranges are valid, congruent and nonoverlapping

PASS: hook ELF32 ARM/uClibc libc.so.0, SONAME, constructor and five native symbols

ORIGINAL_STOCK_SHA256 b2e32b82a37667500ca4f1c8266604bf28cc923ac94343907eb68c843d92e0a1

PATCHED_ELF_SHA256 0e63050bdd63bebb0d14f8f751b1e920f2679da375b0498a1ace06a2ba376039

LIBSDH_SO_SHA256 6e70f606501354267567873ec75d291914a5f946a04be3730dc4f085575d1bd9

PASS: STEP142 STATIC PATCHED ELF AUDIT

NOT VERIFIED: actual loader startup, target ABI call safety, native callback concurrency, physical recovery

BLOCKED FOR FLASH: isolated static build audit is not device deployment authorization



\===== PATCHED ELF PROGRAM HEADERS =====



Elf file type is EXEC (Executable file)

Entry point 0x1957c

There are 8 program headers, starting at offset 52



Program Headers:

  Type           Offset   VirtAddr   PhysAddr   FileSiz MemSiz  Flg Align

  ARM_EXIDX      0x113118 0x00123118 0x00123118 0x00318 0x00318 R   0x4

  PHDR           0x000034 0x00010034 0x00010034 0x00100 0x00100 R E 0x4

  INTERP         0x000134 0x00010134 0x00010134 0x00014 0x00014 R   0x1

      [Requesting program interpreter: /lib/ld-uClibc.so.0]

  LOAD           0x000000 0x00010000 0x00010000 0x116390 0x116390 R E 0x10000

  LOAD           0x123fec 0x00133fec 0x00133fec 0x066c4 0x08660 RW  0x10000

  DYNAMIC        0x125ec8 0x00135ec8 0x00135ec8 0x00138 0x00138 RW  0x4

  GNU_STACK      0x000000 0x00000000 0x00000000 0x00000 0x00000 RW  0x10

  GNU_RELRO      0x123fec 0x00133fec 0x00133fec 0x02014 0x02014 R   0x1



 Section to Segment mapping:

  Segment Sections...

   00     .ARM.exidx 

   01     

   02     .interp 

   03     .interp .hash .dynsym .dynstr .gnu.version .gnu.version_r .rel.dyn .rel.plt .init .plt .text .fini .rodata .ARM.extab .ARM.exidx .eh_frame 

   04     .init_array .fini_array .jcr .data.rel.ro .dynamic .got .data .bss 

   05     .dynamic 

   06     

   07     .init_array .fini_array .jcr .data.rel.ro .dynamic 



\===== PATCHED ELF DYNAMIC TAGS =====



Dynamic section at offset 0x125ec8 contains 36 entries:

  Tag        Type                         Name/Value

 0x00000001 (NEEDED)                     Shared library: [libSdCommon.so]

 0x00000001 (NEEDED)                     Shared library: [libstdc++.so.6]

 0x00000001 (NEEDED)                     Shared library: [libdns_sd.so]

 0x00000001 (NEEDED)                     Shared library: [libSdUtils.so]

 0x00000001 (NEEDED)                     Shared library: [libfdk-aac.so.2]

 0x00000001 (NEEDED)                     Shared library: [libopus.so.0]

 0x00000001 (NEEDED)                     Shared library: [libasound.so.2]

 0x00000001 (NEEDED)                     Shared library: [libusb-1.0.so.0]

 0x00000001 (NEEDED)                     Shared library: [libexecinfo.so]

 0x00000001 (NEEDED)                     Shared library: [libgcc_s.so.1]

 0x00000001 (NEEDED)                     Shared library: [libc.so.0]

 0x0000000c (INIT)                       0x17e88

 0x0000000d (FINI)                       0xf09d0

 0x00000019 (INIT_ARRAY)                 0x133fec

 0x0000001b (INIT_ARRAYSZ)               8 (bytes)

 0x0000001a (FINI_ARRAY)                 0x133ff4

 0x0000001c (FINI_ARRAYSZ)               8 (bytes)

 0x00000004 (HASH)                       0x10148

 0x00000005 (STRTAB)                     0x123434

 0x00000006 (SYMTAB)                     0x113c4

 0x0000000a (STRSZ)                      12124 (bytes)

 0x0000000b (SYMENT)                     16 (bytes)

 0x00000015 (DEBUG)                      0x0

 0x00000003 (PLTGOT)                     0x136000

 0x00000002 (PLTRELSZ)                   3128 (bytes)

 0x00000014 (PLTREL)                     REL

 0x00000017 (JMPREL)                     0x17250

 0x00000011 (REL)                        0x171e8

 0x00000012 (RELSZ)                      104 (bytes)

 0x00000013 (RELENT)                     8 (bytes)

 0x6ffffffe (VERNEED)                    0x17178

 0x6fffffff (VERNEEDNUM)                 2

 0x6ffffff0 (VERSYM)                     0x16c4e

 0x00000001 (NEEDED)                     Shared library: [libSdH.so]

 0x0000001d (RUNPATH)                    Library runpath: [$ORIGIN]

 0x00000000 (NULL)                       0x0



\===== PATCHED ELF RELOCATIONS =====



Relocation section '.rel.dyn' at offset 0x71e8 contains 13 entries:

 Offset     Info    Type                Sym. Value  Symbol's Name

00136660  00001b15 R_ARM_GLOB_DAT         00000000   mfi_certificate

001367b0  0000fa15 R_ARM_GLOB_DAT         00000000   \_\_ctype_toupper

00136804  00014215 R_ARM_GLOB_DAT         00000000   \_\_ctype_tolower

00136858  00018015 R_ARM_GLOB_DAT         00000000   mfi_cert_len

0013688c  0001a715 R_ARM_GLOB_DAT         00000000   stdout

00136890  0001a915 R_ARM_GLOB_DAT         00000000   in6addr_any

001368b0  0001c415 R_ARM_GLOB_DAT         00000000   stderr

001368fc  0001f215 R_ARM_GLOB_DAT         00000000   \_\_ctype_b

001350cc  0000e214 R_ARM_COPY             001350cc   \_ZTVN10__cxxabiv117__class_type_infoE\@CXXABI_1.3

001350f8  0001a814 R_ARM_COPY             001350f8   \_ZTVN10__cxxabiv120__si_class_type_infoE\@CXXABI_1.3

00135124  00024814 R_ARM_COPY             00135124   \_ZTVN10__cxxabiv121__vmi_class_type_infoE\@CXXABI_1.3

00135150  00024a14 R_ARM_COPY             00135150   \_ZTI6Thread

00135158  00025e14 R_ARM_COPY             00135158   \_ZTI12StateMachine



Relocation section '.rel.plt' at offset 0x7250 contains 391 entries:

 Offset     Info    Type                Sym. Value  Symbol's Name

0013600c  00000116 R_ARM_JUMP_SLOT        00000000   libusb_free_config_descriptor

00136010  00000216 R_ARM_JUMP_SLOT        00000000   start_timer

00136014  00000416 R_ARM_JUMP_SLOT        00000000   prop_get_int

00136018  00000516 R_ARM_JUMP_SLOT        00000000   pthread_cond_signal

0013601c  00000916 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_d2uiz\@GCC_3.5

00136020  00000c16 R_ARM_JUMP_SLOT        00000000   \_ZN13SoftAPService8instanceEv

00136024  00000e16 R_ARM_JUMP_SLOT        00000000   \_Znwj\@GLIBCXX_3.4

00136028  00000f16 R_ARM_JUMP_SLOT        00000000   snd_pcm_status_sizeof

0013602c  00001416 R_ARM_JUMP_SLOT        00000000   strncasecmp

00136030  00001616 R_ARM_JUMP_SLOT        00000000   signal

00136034  00001716 R_ARM_JUMP_SLOT        00000000   snd_pcm_close

00136038  00001816 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_uldivmod\@GCC_3.5

0013603c  00001c16 R_ARM_JUMP_SLOT        00000000   remove_apple_gadget

00136040  00001d16 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_dcmpeq\@GCC_3.5

00136044  00001e16 R_ARM_JUMP_SLOT        00000000   connect

00136048  00001f16 R_ARM_JUMP_SLOT        00000000   strncpy

0013604c  00002116 R_ARM_JUMP_SLOT        00000000   realpath

00136050  00002316 R_ARM_JUMP_SLOT        00000000   exit

00136054  00002416 R_ARM_JUMP_SLOT        00000000   strlen

00136058  00002816 R_ARM_JUMP_SLOT        00000000   select

0013605c  00002916 R_ARM_JUMP_SLOT        00000000   check_net_interface_is_up

00136060  00002a16 R_ARM_JUMP_SLOT        00000000   printf

00136064  00002b16 R_ARM_JUMP_SLOT        00000000   \_ZN9HeartBeatC1Ev

00136068  00002f16 R_ARM_JUMP_SLOT        00000000   snd_pcm_hw_params_set_periods

0013606c  00003016 R_ARM_JUMP_SLOT        00000000   strdup

00136070  00003216 R_ARM_JUMP_SLOT        00000000   \_ZN12ScreenRecordD1Ev

00136074  00003516 R_ARM_JUMP_SLOT        00000000   libusb_has_capability

00136078  00003616 R_ARM_JUMP_SLOT        00000000   \_\_cmsg_nxthdr

0013607c  00003816 R_ARM_JUMP_SLOT        00000000   libusb_open

00136080  00003916 R_ARM_JUMP_SLOT        00000000   DNSServiceReconfirmRecord

00136084  00003a16 R_ARM_JUMP_SLOT        00000000   \_\_bswapsi2\@GCC_4.3.0

00136088  00003c16 R_ARM_JUMP_SLOT        00000000   gmtime_r

0013608c  00003e16 R_ARM_JUMP_SLOT        00000000   free

00136090  00003f16 R_ARM_JUMP_SLOT        00000000   abort

00136094  00004016 R_ARM_JUMP_SLOT        00000000   \_ZN10AoaService14addAoaListenerEP12IAoaListener

00136098  00004116 R_ARM_JUMP_SLOT        00000000   memmove

0013609c  00004216 R_ARM_JUMP_SLOT        00000000   aacDecoder_SetParam

001360a0  00004616 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_fcmple\@GCC_3.5

001360a4  00004816 R_ARM_JUMP_SLOT        00000000   \_ZN9HeartBeat5startEv

001360a8  00004d16 R_ARM_JUMP_SLOT        00000000   TXTRecordGetBytesPtr

001360ac  00004e16 R_ARM_JUMP_SLOT        00000000   \_ZN12StateMachine12registStatesEP7SFStatePKci

001360b0  00004f16 R_ARM_JUMP_SLOT        00000000   fork

001360b4  00005016 R_ARM_JUMP_SLOT        00000000   create_timer

001360b8  00005116 R_ARM_JUMP_SLOT        00000000   opus_decode

001360bc  00005216 R_ARM_JUMP_SLOT        00000000   snd_pcm_open

001360c0  00005416 R_ARM_JUMP_SLOT        00000000   getIpAddress

001360c4  00005a16 R_ARM_JUMP_SLOT        00000000   pthread_mutex_init

001360c8  00005b16 R_ARM_JUMP_SLOT        00000000   get_sps_pps_size

001360cc  00005e16 R_ARM_JUMP_SLOT        00000000   \_ZNKSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEE6substrEjj\@GLIBCXX_3.4.21

001360d0  00005f16 R_ARM_JUMP_SLOT        00000000   pthread_create

001360d4  00006016 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_i2f\@GCC_3.5

001360d8  00006216 R_ARM_JUMP_SLOT        00000000   fprintf

001360dc  00006316 R_ARM_JUMP_SLOT        00000000   libusb_detach_kernel_driver

001360e0  00006416 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_dcmpge\@GCC_3.5

001360e4  00006516 R_ARM_JUMP_SLOT        00000000   TXTRecordGetValuePtr

001360e8  00006616 R_ARM_JUMP_SLOT        00000000   strpbrk

001360ec  00006716 R_ARM_JUMP_SLOT        00000000   iap2_get_config_string

001360f0  00006916 R_ARM_JUMP_SLOT        00000000   strsep

001360f4  00006a16 R_ARM_JUMP_SLOT        00000000   freeifaddrs

001360f8  00006d16 R_ARM_JUMP_SLOT        00000000   \_ZN9Semaphore4downEv

001360fc  00007116 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_dmul\@GCC_3.5

00136100  00007216 R_ARM_JUMP_SLOT        00000000   \_\_cxa_begin_catch\@CXXABI_1.3

00136104  00007316 R_ARM_JUMP_SLOT        00000000   setvbuf

00136108  00007516 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_uidivmod\@GCC_3.5

0013610c  00007716 R_ARM_JUMP_SLOT        00000000   switch_board_mode

00136110  00007916 R_ARM_JUMP_SLOT        00000000   set_timer_timeout_callback

00136114  00007a16 R_ARM_JUMP_SLOT        00000000   atoi

00136118  00007b16 R_ARM_JUMP_SLOT        00000000   libusb_get_device_list

0013611c  00007c16 R_ARM_JUMP_SLOT        00000000   pthread_cond_broadcast

00136120  00007d16 R_ARM_JUMP_SLOT        00000000   getpeername

00136124  00007e16 R_ARM_JUMP_SLOT        00000000   puts

00136128  00008116 R_ARM_JUMP_SLOT        00000000   snd_pcm_status_get_delay

0013612c  00008216 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_ui2f\@GCC_3.5

00136130  00008416 R_ARM_JUMP_SLOT        00000000   pthread_cond_destroy

00136134  00008516 R_ARM_JUMP_SLOT        00018224   \_ZN12StateMachine3runEv

00136138  00008616 R_ARM_JUMP_SLOT        00000000   delete_timer

0013613c  00008716 R_ARM_JUMP_SLOT        00000000   \_ZN10AoaService19usbSwitchNormalModeEv

00136140  00008916 R_ARM_JUMP_SLOT        00000000   libusb_control_transfer

00136144  00008d16 R_ARM_JUMP_SLOT        00000000   \_\_uClibc_main

00136148  00009016 R_ARM_JUMP_SLOT        00000000   is_driver_loaded

0013614c  00009116 R_ARM_JUMP_SLOT        00000000   \_ZN12StateMachineD2Ev

00136150  00009316 R_ARM_JUMP_SLOT        00000000   fcntl

00136154  00009416 R_ARM_JUMP_SLOT        00000000   vasprintf

00136158  00009516 R_ARM_JUMP_SLOT        00000000   libusb_error_name

0013615c  00009616 R_ARM_JUMP_SLOT        00000000   shutdown

00136160  00009716 R_ARM_JUMP_SLOT        00000000   pthread_self

00136164  00009816 R_ARM_JUMP_SLOT        00000000   \_ZN6Thread5startEv

00136168  00009a16 R_ARM_JUMP_SLOT        00000000   get_ak3918_serial_number

0013616c  00009e16 R_ARM_JUMP_SLOT        00000000   syslog

00136170  00009f16 R_ARM_JUMP_SLOT        00000000   remove

00136174  0000a016 R_ARM_JUMP_SLOT        00000000   asprintf

00136178  0000a116 R_ARM_JUMP_SLOT        00000000   \_ZN10AoaServiceC1Ei

0013617c  0000a216 R_ARM_JUMP_SLOT        00000000   pthread_key_create

00136180  0000a316 R_ARM_JUMP_SLOT        00000000   libusb_reset_device

00136184  0000a816 R_ARM_JUMP_SLOT        00000000   \_ZNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEE9_M_assignERKS4\_@GLIBCXX_3.4.21

00136188  0000a916 R_ARM_JUMP_SLOT        00000000   cfg_do_set

0013618c  0000ab16 R_ARM_JUMP_SLOT        00000000   snd_pcm_drain

00136190  0000ac16 R_ARM_JUMP_SLOT        00000000   ioctl

00136194  0000ad16 R_ARM_JUMP_SLOT        00000000   libusb_exit

00136198  0000ae16 R_ARM_JUMP_SLOT        00000000   sem_wait

0013619c  0000af16 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_i2d\@GCC_3.5

001361a0  0000b016 R_ARM_JUMP_SLOT        00000000   sem_init

001361a4  0000b116 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_ddiv\@GCC_3.5

001361a8  0000b216 R_ARM_JUMP_SLOT        00000000   sleep

001361ac  0000b316 R_ARM_JUMP_SLOT        00000000   TXTRecordCreate

001361b0  0000b816 R_ARM_JUMP_SLOT        00000000   build_apple_gadget

001361b4  0000bb16 R_ARM_JUMP_SLOT        00000000   \_Z17led_manager_startii

001361b8  0000bd16 R_ARM_JUMP_SLOT        00000000   print_hex

001361bc  0000be16 R_ARM_JUMP_SLOT        00000000   \_\_register_frame_info

001361c0  0000c316 R_ARM_JUMP_SLOT        00000000   snprintf

001361c4  0000c416 R_ARM_JUMP_SLOT        00000000   send

001361c8  0000c516 R_ARM_JUMP_SLOT        00000000   fseeko

001361cc  0000c716 R_ARM_JUMP_SLOT        00000000   sscanf

001361d0  0000c816 R_ARM_JUMP_SLOT        00000000   backtrace_symbols

001361d4  0000ca16 R_ARM_JUMP_SLOT        00000000   getuid

001361d8  0000cb16 R_ARM_JUMP_SLOT        00000000   getpid

001361dc  0000cc16 R_ARM_JUMP_SLOT        00000000   getpwuid_r

001361e0  0000ce16 R_ARM_JUMP_SLOT        00000000   \_ZN12StateMachineC2Eii

001361e4  0000cf16 R_ARM_JUMP_SLOT        00000000   libusb_free_device_list

001361e8  0000d216 R_ARM_JUMP_SLOT        00000000   \_ZN6ThreadD2Ev

001361ec  0000d416 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_f2d\@GCC_3.5

001361f0  0000d716 R_ARM_JUMP_SLOT        00000000   getifaddrs

001361f4  0000d816 R_ARM_JUMP_SLOT        00000000   pthread_getspecific

001361f8  0000d916 R_ARM_JUMP_SLOT        00000000   fread

001361fc  0000db16 R_ARM_JUMP_SLOT        00000000   strcmp

00136200  0000dc16 R_ARM_JUMP_SLOT        00000000   sem_destroy

00136204  0000de16 R_ARM_JUMP_SLOT        00000000   munmap

00136208  0000df16 R_ARM_JUMP_SLOT        00000000   libusb_unlock_events

0013620c  0000e116 R_ARM_JUMP_SLOT        00000000   \_ZN9BtService19addBtNotifyListenerEP17IBtNotifyListener

00136210  0000e316 R_ARM_JUMP_SLOT        00000000   \_ZSt19__throw_logic_errorPKc\@GLIBCXX_3.4

00136214  0000e416 R_ARM_JUMP_SLOT        00000000   prop_set_int

00136218  0000e816 R_ARM_JUMP_SLOT        00000000   dlopen

0013621c  0000e916 R_ARM_JUMP_SLOT        00000000   aacDecoder_DecodeFrame

00136220  0000ec16 R_ARM_JUMP_SLOT        00000000   pthread_mutex_unlock

00136224  0000ee16 R_ARM_JUMP_SLOT        00000000   getsockopt

00136228  0000ef16 R_ARM_JUMP_SLOT        00000000   mmap

0013622c  0000f016 R_ARM_JUMP_SLOT        00000000   pthread_setschedparam

00136230  0000f116 R_ARM_JUMP_SLOT        00000000   snd_pcm_recover

00136234  0000f316 R_ARM_JUMP_SLOT        00000000   snd_pcm_hw_params

00136238  0000f516 R_ARM_JUMP_SLOT        00000000   snd_pcm_wait

0013623c  0000f616 R_ARM_JUMP_SLOT        00000000   snd_pcm_hw_params_set_format

00136240  0000f716 R_ARM_JUMP_SLOT        00000000   recv

00136244  0000f916 R_ARM_JUMP_SLOT        00000000   mfi_process_challenge

00136248  0000fe16 R_ARM_JUMP_SLOT        00000000   mfi_get_certificate

0013624c  0000ff16 R_ARM_JUMP_SLOT        00000000   \_ZN9BtService11btReconnectEv

00136250  00010016 R_ARM_JUMP_SLOT        00000000   pthread_key_delete

00136254  00010116 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_dcmplt\@GCC_3.5

00136258  00010216 R_ARM_JUMP_SLOT        00000000   strrchr

0013625c  00010316 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_dcmple\@GCC_3.5

00136260  00010416 R_ARM_JUMP_SLOT        00000000   prop_get_string

00136264  00010616 R_ARM_JUMP_SLOT        00000000   \_ZN6Thread4joinEv

00136268  00010716 R_ARM_JUMP_SLOT        00000000   backtrace

0013626c  00010816 R_ARM_JUMP_SLOT        00000000   ftruncate

00136270  00010916 R_ARM_JUMP_SLOT        00000000   sysconf

00136274  00010a16 R_ARM_JUMP_SLOT        00000000   pthread_attr_init

00136278  00010e16 R_ARM_JUMP_SLOT        00000000   memset

0013627c  00011016 R_ARM_JUMP_SLOT        00000000   tolower

00136280  00011116 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_d2lz\@GCC_3.5

00136284  00011216 R_ARM_JUMP_SLOT        00000000   open_local_socket

00136288  00011316 R_ARM_JUMP_SLOT        00000000   read

0013628c  00011416 R_ARM_JUMP_SLOT        00000000   strndup

00136290  00011716 R_ARM_JUMP_SLOT        00000000   \_ZN9SemaphoreC1Ev

00136294  00011816 R_ARM_JUMP_SLOT        00000000   listen

00136298  00011916 R_ARM_JUMP_SLOT        00000000   snd_pcm_hw_params_malloc

0013629c  00011b16 R_ARM_JUMP_SLOT        00000000   unlink

001362a0  00011c16 R_ARM_JUMP_SLOT        00000000   perror

001362a4  00011d16 R_ARM_JUMP_SLOT        00000000   fflush

001362a8  00012116 R_ARM_JUMP_SLOT        00000000   aacDecoder_Close

001362ac  00012216 R_ARM_JUMP_SLOT        00000000   snd_pcm_prepare

001362b0  00012316 R_ARM_JUMP_SLOT        00000000   opus_encoder_create

001362b4  00012416 R_ARM_JUMP_SLOT        00000000   fopen

001362b8  00012516 R_ARM_JUMP_SLOT        00000000   pthread_cond_init

001362bc  00012616 R_ARM_JUMP_SLOT        00000000   strcpy

001362c0  00012716 R_ARM_JUMP_SLOT        00000000   bzero

001362c4  00012816 R_ARM_JUMP_SLOT        00000000   check_net_interface_is_exist

001362c8  00012916 R_ARM_JUMP_SLOT        00000000   \_\_errno_location

001362cc  00012a16 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_fdiv\@GCC_3.5

001362d0  00012c16 R_ARM_JUMP_SLOT        00000000   fscanf

001362d4  00012e16 R_ARM_JUMP_SLOT        00000000   \_ZdlPv\@GLIBCXX_3.4

001362d8  00012f16 R_ARM_JUMP_SLOT        00000000   write

001362dc  00013016 R_ARM_JUMP_SLOT        00000000   \_ZNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEpLEPKc\@GLIBCXX_3.4.21

001362e0  00013116 R_ARM_JUMP_SLOT        00000000   mkstemp

001362e4  00013316 R_ARM_JUMP_SLOT        00000000   time

001362e8  00013416 R_ARM_JUMP_SLOT        00000000   libusb_hotplug_register_callback

001362ec  00013516 R_ARM_JUMP_SLOT        00000000   fwrite

001362f0  00013616 R_ARM_JUMP_SLOT        00000000   pthread_mutex_lock

001362f4  00013716 R_ARM_JUMP_SLOT        00000000   opus_decoder_create

001362f8  00013816 R_ARM_JUMP_SLOT        00000000   memchr

001362fc  00013916 R_ARM_JUMP_SLOT        00000000   DNSServiceQueryRecord

00136300  00013a16 R_ARM_JUMP_SLOT        00000000   TXTRecordGetLength

00136304  00013e16 R_ARM_JUMP_SLOT        00000000   pthread_attr_setstacksize

00136308  00014016 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_l2f\@GCC_3.5

0013630c  00014316 R_ARM_JUMP_SLOT        00000000   memcmp

00136310  00014516 R_ARM_JUMP_SLOT        00000000   fseek

00136314  00014616 R_ARM_JUMP_SLOT        00000000   pthread_attr_setdetachstate

00136318  00014916 R_ARM_JUMP_SLOT        00000000   \_Z12send_versionh

0013631c  00014a16 R_ARM_JUMP_SLOT        00000000   inet_ntop

00136320  00014b16 R_ARM_JUMP_SLOT        00000000   DNSServiceBrowse

00136324  00014c16 R_ARM_JUMP_SLOT        00000000   writen

00136328  00015016 R_ARM_JUMP_SLOT        00000000   fsync

0013632c  00015316 R_ARM_JUMP_SLOT        00000000   getsockname

00136330  00015616 R_ARM_JUMP_SLOT        00000000   strftime

00136334  00015716 R_ARM_JUMP_SLOT        00000000   rename

00136338  00015816 R_ARM_JUMP_SLOT        00000000   check_board_auth

0013633c  00015a16 R_ARM_JUMP_SLOT        00000000   libusb_hotplug_deregister_callback

00136340  00015b16 R_ARM_JUMP_SLOT        00000000   if_indextoname

00136344  00015c16 R_ARM_JUMP_SLOT        00000000   \_ZN9BtServiceD1Ev

00136348  00015d16 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_d2ulz\@GCC_3.5

0013634c  00015e16 R_ARM_JUMP_SLOT        00000000   snd_pcm_get_params

00136350  00016116 R_ARM_JUMP_SLOT        00000000   \_ZNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEE13_S_copy_charsEPcPKcS7\_@GLIBCXX_3.4.21

00136354  00016216 R_ARM_JUMP_SLOT        00000000   pthread_getschedparam

00136358  00016316 R_ARM_JUMP_SLOT        00000000   libusb_interrupt_transfer

0013635c  00016616 R_ARM_JUMP_SLOT        00000000   \_\_cxa_end_cleanup\@CXXABI_1.3

00136360  00016716 R_ARM_JUMP_SLOT        00000000   libusb_get_device_descriptor

00136364  00016816 R_ARM_JUMP_SLOT        00000000   snd_pcm_hw_params_any

00136368  00016a16 R_ARM_JUMP_SLOT        00000000   pthread_mutex_destroy

0013636c  00016b16 R_ARM_JUMP_SLOT        00000000   strtol

00136370  00016c16 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_fmul\@GCC_3.5

00136374  00016e16 R_ARM_JUMP_SLOT        00000000   aacDecoder_Fill

00136378  00016f16 R_ARM_JUMP_SLOT        00000000   \_ZN10AoaServiceD1Ev

0013637c  00017016 R_ARM_JUMP_SLOT        00000000   opus_encoder_destroy

00136380  00017216 R_ARM_JUMP_SLOT        00000000   strcasecmp

00136384  00017316 R_ARM_JUMP_SLOT        00000000   malloc

00136388  00017416 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_dsub\@GCC_3.5

0013638c  00017516 R_ARM_JUMP_SLOT        00000000   DNSServiceRefSockFD

00136390  00017616 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_ldivmod\@GCC_3.5

00136394  00017716 R_ARM_JUMP_SLOT        00000000   gettimeofday

00136398  00017916 R_ARM_JUMP_SLOT        00000000   libusb_claim_interface

0013639c  00017b16 R_ARM_JUMP_SLOT        00000000   libusb_bulk_transfer

001363a0  00017e16 R_ARM_JUMP_SLOT        00000000   snd_strerror

001363a4  00017f16 R_ARM_JUMP_SLOT        00000000   \_ZN13SoftAPServiceD1Ev

001363a8  00018116 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_dadd\@GCC_3.5

001363ac  00018216 R_ARM_JUMP_SLOT        00000000   nanosleep

001363b0  00018416 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_f2uiz\@GCC_3.5

001363b4  00018516 R_ARM_JUMP_SLOT        00000000   calloc

001363b8  00018616 R_ARM_JUMP_SLOT        00000000   snd_pcm_name

001363bc  00018716 R_ARM_JUMP_SLOT        00000000   \_ZN9BtService5startEv

001363c0  00018b16 R_ARM_JUMP_SLOT        00000000   \_ZN9SemaphoreD1Ev

001363c4  00018c16 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_f2iz\@GCC_3.5

001363c8  00018f16 R_ARM_JUMP_SLOT        00000000   cfg_get_int

001363cc  00019016 R_ARM_JUMP_SLOT        00000000   ark_get_info_int

001363d0  00019116 R_ARM_JUMP_SLOT        00000000   aacDecoder_Open

001363d4  00019316 R_ARM_JUMP_SLOT        00000000   \_ZNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEE10_M_disposeEv\@GLIBCXX_3.4.21

001363d8  00019516 R_ARM_JUMP_SLOT        00000000   sem_post

001363dc  00019616 R_ARM_JUMP_SLOT        00000000   ark_set_info

001363e0  00019716 R_ARM_JUMP_SLOT        00000000   pthread_cond_wait

001363e4  00019816 R_ARM_JUMP_SLOT        00000000   libusb_handle_events_completed

001363e8  00019916 R_ARM_JUMP_SLOT        00000000   \_ZN5MutexD1Ev

001363ec  00019b16 R_ARM_JUMP_SLOT        00000000   rand

001363f0  00019c16 R_ARM_JUMP_SLOT        00000000   strcspn

001363f4  00019d16 R_ARM_JUMP_SLOT        00000000   \_Z16get_auth_status1v

001363f8  00019e16 R_ARM_JUMP_SLOT        00000000   recvmsg

001363fc  0001a016 R_ARM_JUMP_SLOT        00000000   fstat

00136400  0001a116 R_ARM_JUMP_SLOT        00000000   libusb_close

00136404  0001a216 R_ARM_JUMP_SLOT        00000000   memcpy

00136408  0001a516 R_ARM_JUMP_SLOT        00000000   usleep

0013640c  0001a616 R_ARM_JUMP_SLOT        00000000   DNSServiceUpdateRecord

00136410  0001aa16 R_ARM_JUMP_SLOT        00000000   \_ZN9BtService6btOpenEv

00136414  0001ab16 R_ARM_JUMP_SLOT        00000000   strnlen

00136418  0001ad16 R_ARM_JUMP_SLOT        00000000   DNSServiceRegister

0013641c  0001af16 R_ARM_JUMP_SLOT        00000000   TXTRecordDeallocate

00136420  0001b016 R_ARM_JUMP_SLOT        00000000   iap2_get_config_int

00136424  0001b116 R_ARM_JUMP_SLOT        00000000   \_ZN9BtService12btModifyNameERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEE

00136428  0001b316 R_ARM_JUMP_SLOT        00000000   popen

0013642c  0001b416 R_ARM_JUMP_SLOT        00000000   nftw

00136430  0001b516 R_ARM_JUMP_SLOT        00000000   pclose

00136434  0001b616 R_ARM_JUMP_SLOT        00000000   opus_encode

00136438  0001b816 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_idivmod\@GCC_3.5

0013643c  0001bb16 R_ARM_JUMP_SLOT        00000000   localtime

00136440  0001bd16 R_ARM_JUMP_SLOT        00000000   waitpid

00136444  0001be16 R_ARM_JUMP_SLOT        00000000   fileno

00136448  0001c016 R_ARM_JUMP_SLOT        00000000   DNSServiceResolve

0013644c  0001c116 R_ARM_JUMP_SLOT        00000000   snd_pcm_hw_params_set_rate

00136450  0001c216 R_ARM_JUMP_SLOT        00000000   writev

00136454  0001c316 R_ARM_JUMP_SLOT        00000000   libusb_kernel_driver_active

00136458  0001c616 R_ARM_JUMP_SLOT        00000000   \_ZN9HeartBeatD1Ev

0013645c  0001c916 R_ARM_JUMP_SLOT        00000000   snd_pcm_writei

00136460  0001cb16 R_ARM_JUMP_SLOT        00000000   dlclose

00136464  0001cc16 R_ARM_JUMP_SLOT        00000000   prop_set_string

00136468  0001cd16 R_ARM_JUMP_SLOT        00000000   clock_gettime

0013646c  0001cf16 R_ARM_JUMP_SLOT        00000000   DNSServiceCreateConnection

00136470  0001d116 R_ARM_JUMP_SLOT        00000000   random

00136474  0001d316 R_ARM_JUMP_SLOT        00000000   putchar

00136478  0001d416 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_fsub\@GCC_3.5

0013647c  0001d716 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_uidiv\@GCC_3.5

00136480  0001d816 R_ARM_JUMP_SLOT        00000000   \_\_deregister_frame_info

00136484  0001da16 R_ARM_JUMP_SLOT        00000000   snd_pcm_hw_params_set_access

00136488  0001db16 R_ARM_JUMP_SLOT        00000000   mkdir

0013648c  0001dd16 R_ARM_JUMP_SLOT        00000000   \_ZN12StateMachine9procStateEP9StateQEvt

00136490  0001de16 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_idiv\@GCC_3.5

00136494  0001df16 R_ARM_JUMP_SLOT        00000000   snd_pcm_hw_params_set_period_size

00136498  0001e016 R_ARM_JUMP_SLOT        00000000   pipe

0013649c  0001e516 R_ARM_JUMP_SLOT        00000000   libusb_set_auto_detach_kernel_driver

001364a0  0001e616 R_ARM_JUMP_SLOT        00000000   \_\_cxa_rethrow\@CXXABI_1.3

001364a4  0001e716 R_ARM_JUMP_SLOT        00000000   dlsym

001364a8  0001e816 R_ARM_JUMP_SLOT        00000000   opus_decoder_destroy

001364ac  0001e916 R_ARM_JUMP_SLOT        00000000   timestamp_ext

001364b0  0001eb16 R_ARM_JUMP_SLOT        00000000   snd_pcm_status_get_htstamp

001364b4  0001ec16 R_ARM_JUMP_SLOT        00000000   pthread_cond_timedwait

001364b8  0001ef16 R_ARM_JUMP_SLOT        00000000   kill

001364bc  0001f316 R_ARM_JUMP_SLOT        00000000   sendto

001364c0  0001f416 R_ARM_JUMP_SLOT        00000000   libusb_init

001364c4  0001f516 R_ARM_JUMP_SLOT        00000000   open

001364c8  0001f716 R_ARM_JUMP_SLOT        00000000   \_ZN12ScreenRecordC1EP22IScreenRecordCallbacksiii

001364cc  0001f816 R_ARM_JUMP_SLOT        00000000   snd_pcm_hw_params_set_channels

001364d0  0001fa16 R_ARM_JUMP_SLOT        00000000   bind

001364d4  0001fb16 R_ARM_JUMP_SLOT        00000000   ark_set_info_int

001364d8  0001fc16 R_ARM_JUMP_SLOT        00000000   setsockopt

001364dc  0001ff16 R_ARM_JUMP_SLOT        00000000   \_ZNSt8ios_base4InitC1Ev\@GLIBCXX_3.4

001364e0  00020016 R_ARM_JUMP_SLOT        00000000   socket

001364e4  00020216 R_ARM_JUMP_SLOT        00000000   ark_get_info_string

001364e8  00020416 R_ARM_JUMP_SLOT        00000000   TXTRecordSetValue

001364ec  00020516 R_ARM_JUMP_SLOT        00000000   snd_pcm_status

001364f0  00020616 R_ARM_JUMP_SLOT        00000000   floor

001364f4  00020c16 R_ARM_JUMP_SLOT        00000000   strtof

001364f8  00020d16 R_ARM_JUMP_SLOT        00000000   access

001364fc  00020f16 R_ARM_JUMP_SLOT        00000000   \_ZN9BtService7btCloseEv

00136500  00021016 R_ARM_JUMP_SLOT        00000000   sprintf

00136504  00021216 R_ARM_JUMP_SLOT        00000000   \_ZN8AutolockD1Ev

00136508  00021316 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_ul2d\@GCC_3.5

0013650c  00021416 R_ARM_JUMP_SLOT        00000000   \_Z21register_auto_key_cbsPvS\_

00136510  00021516 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_ui2d\@GCC_3.5
00136514  00021616 R_ARM_JUMP_SLOT        00000000   vsnprintf

00136518  00021b16 R_ARM_JUMP_SLOT        00000000   chmod

0013651c  00021c16 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_d2iz\@GCC_3.5

00136520  00021d16 R_ARM_JUMP_SLOT        00000000   ftello

00136524  00021e16 R_ARM_JUMP_SLOT        00000000   fclose

00136528  00021f16 R_ARM_JUMP_SLOT        00000000   process_is_launcher

0013652c  00022016 R_ARM_JUMP_SLOT        00000000   feof

00136530  00022416 R_ARM_JUMP_SLOT        00000000   \_\_cxa_end_catch\@CXXABI_1.3

00136534  00022516 R_ARM_JUMP_SLOT        00000000   strtoul

00136538  00022716 R_ARM_JUMP_SLOT        00000000   \_\_gxx_personality_v0\@CXXABI_1.3

0013653c  00022a16 R_ARM_JUMP_SLOT        00000000   get_current_mono_time_ms

00136540  00022c16 R_ARM_JUMP_SLOT        00000000   getpwnam

00136544  00022e16 R_ARM_JUMP_SLOT        00000000   powf

00136548  00022f16 R_ARM_JUMP_SLOT        00000000   stat

0013654c  00023016 R_ARM_JUMP_SLOT        00000000   close

00136550  00023216 R_ARM_JUMP_SLOT        00000000   fgets

00136554  00023416 R_ARM_JUMP_SLOT        00000000   recvfrom

00136558  00023616 R_ARM_JUMP_SLOT        00000000   fputc

0013655c  00023716 R_ARM_JUMP_SLOT        00000000   strstr

00136560  00023816 R_ARM_JUMP_SLOT        00000000   strcasestr

00136564  00023916 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_l2d\@GCC_3.5

00136568  00023a16 R_ARM_JUMP_SLOT        00000000   realloc

0013656c  00023b16 R_ARM_JUMP_SLOT        00000000   strchr

00136570  00023d16 R_ARM_JUMP_SLOT        00000000   fputs

00136574  00023f16 R_ARM_JUMP_SLOT        00000000   \_ZNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEE9_M_createERjj\@GLIBCXX_3.4.21

00136578  00024016 R_ARM_JUMP_SLOT        00000000   stop_timer

0013657c  00024216 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_dcmpgt\@GCC_3.5

00136580  00024316 R_ARM_JUMP_SLOT        00000000   opus_encoder_ctl

00136584  00024516 R_ARM_JUMP_SLOT        00000000   \_ZN9BtService8instanceEv

00136588  00024616 R_ARM_JUMP_SLOT        00000000   \_Z19register_cp_key_cbsPvS\_

0013658c  00024716 R_ARM_JUMP_SLOT        00000000   strncmp

00136590  00024c16 R_ARM_JUMP_SLOT        00000000   DNSServiceConstructFullName

00136594  00024e16 R_ARM_JUMP_SLOT        00000000   flock

00136598  00024f16 R_ARM_JUMP_SLOT        00000000   pthread_join

0013659c  00025016 R_ARM_JUMP_SLOT        00000000   if_nametoindex

001365a0  00025116 R_ARM_JUMP_SLOT        00000000   aacDecoder_ConfigRaw

001365a4  00025216 R_ARM_JUMP_SLOT        00000000   accept

001365a8  00025416 R_ARM_JUMP_SLOT        00000000   send_local_message

001365ac  00025516 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_d2f\@GCC_3.5

001365b0  00025816 R_ARM_JUMP_SLOT        00000000   libusb_get_active_config_descriptor

001365b4  00025916 R_ARM_JUMP_SLOT        00000000   DNSServiceProcessResult

001365b8  00025b16 R_ARM_JUMP_SLOT        00000000   mfi_get_serial_num

001365bc  00025d16 R_ARM_JUMP_SLOT        00000000   \_ZN9BtService14rescanBtStatusEv

001365c0  00026116 R_ARM_JUMP_SLOT        00000000   prctl

001365c4  00026316 R_ARM_JUMP_SLOT        00000000   pthread_setspecific

001365c8  00026516 R_ARM_JUMP_SLOT        00000000   strerror

001365cc  00026716 R_ARM_JUMP_SLOT        00000000   cfg_get_string

001365d0  00026816 R_ARM_JUMP_SLOT        00000000   \_\_aeabi_fcmpge\@GCC_3.5

001365d4  00026916 R_ARM_JUMP_SLOT        00000000   getenv

001365d8  00026c16 R_ARM_JUMP_SLOT        00000000   cfg_do_set_int

001365dc  00026e16 R_ARM_JUMP_SLOT        00000000   snd_pcm_readi

001365e0  00026f16 R_ARM_JUMP_SLOT        00000000   libusb_set_configuration

001365e4  00027016 R_ARM_JUMP_SLOT        00000000   getppid

001365e8  00027116 R_ARM_JUMP_SLOT        00000000   snd_pcm_status_get_avail

001365ec  00027216 R_ARM_JUMP_SLOT        00000000   DNSServiceRefDeallocate

001365f0  00027416 R_ARM_JUMP_SLOT        00000000   \_\_assert

001365f4  00027616 R_ARM_JUMP_SLOT        00000000   \_ZN5MutexC1Ev

001365f8  00027816 R_ARM_JUMP_SLOT        00000000   \_ZN9BtService11btCloseSyncEv

001365fc  00027c16 R_ARM_JUMP_SLOT        00000000   system

00136600  00027f16 R_ARM_JUMP_SLOT        00000000   \_ZN9Semaphore2upEv

00136604  00028116 R_ARM_JUMP_SLOT        00000000   \_ZNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEE6appendEPKc\@GLIBCXX_3.4.21

00136608  00028316 R_ARM_JUMP_SLOT        00000000   snd_pcm_hw_params_free

0013660c  00028416 R_ARM_JUMP_SLOT        00000000   \_ZN8AutolockC1EP5Mutex

00136610  00028916 R_ARM_JUMP_SLOT        00000000   ip_address_is_ready

00136614  00028c16 R_ARM_JUMP_SLOT        00000000   \_ZNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEE6appendERKS4\_@GLIBCXX_3.4.21

00136618  00028d16 R_ARM_JUMP_SLOT        00000000   DNSServiceGetAddrInfo

0013661c  00028e16 R_ARM_JUMP_SLOT        00000000   pthread_attr_destroy

00136620  00029016 R_ARM_JUMP_SLOT        00000000   strspn

00136624  00029216 R_ARM_JUMP_SLOT        00000000   \_ZNSt8ios_base4InitD1Ev\@GLIBCXX_3.4



\===== SHIM DYNAMIC LIBRARY HEADERS =====

ELF Header:

  Magic:   7f 45 4c 46 01 01 01 00 00 00 00 00 00 00 00 00 

  Class:                             ELF32

  Data:                              2's complement, little endian

  Version:                           1 (current)

  OS/ABI:                            UNIX - System V

  ABI Version:                       0

  Type:                              DYN (Shared object file)

  Machine:                           ARM

  Version:                           0x1

  Entry point address:               0x0

  Start of program headers:          52 (bytes into file)

  Start of section headers:          26956 (bytes into file)

  Flags:                             0x5000200, Version5 EABI, soft-float ABI

  Size of this header:               52 (bytes)

  Size of program headers:           32 (bytes)

  Number of program headers:         5

  Size of section headers:           40 (bytes)

  Number of section headers:         31

  Section header string table index: 30



\===== SHIM IMPORTS AND SONAME =====



Dynamic section at offset 0x4e54 contains 25 entries:

  Tag        Type                         Name/Value

 0x00000001 (NEEDED)                     Shared library: [libc.so.0]

 0x0000000e (SONAME)                     Library soname: [libSdH.so]

 0x0000000c (INIT)                       0x954

 0x0000000d (FINI)                       0x407c

 0x00000019 (INIT_ARRAY)                 0x5e48

 0x0000001b (INIT_ARRAYSZ)               8 (bytes)

 0x0000001a (FINI_ARRAY)                 0x5e50

 0x0000001c (FINI_ARRAYSZ)               4 (bytes)

 0x00000004 (HASH)                       0xd4

 0x6ffffef5 (GNU_HASH)                   0x230

 0x00000005 (STRTAB)                     0x570

 0x00000006 (SYMTAB)                     0x270

 0x0000000a (STRSZ)                      596 (bytes)

 0x0000000b (SYMENT)                     16 (bytes)

 0x00000003 (PLTGOT)                     0x5f3c

 0x00000002 (PLTRELSZ)                   296 (bytes)

 0x00000014 (PLTREL)                     REL

 0x00000017 (JMPREL)                     0x82c

 0x00000011 (REL)                        0x7c4

 0x00000012 (RELSZ)                      104 (bytes)

 0x00000013 (RELENT)                     8 (bytes)

 0x00000018 (BIND_NOW)                   

 0x6ffffffb (FLAGS_1)                    Flags: NOW

 0x6ffffffa (RELCOUNT)                   4

 0x00000000 (NULL)                       0x0



\===== SHIM EXPORTED AND UNRESOLVED SYMBOLS =====

     0: 00000000     0 NOTYPE  LOCAL  DEFAULT  UND 

     3: 00000000     0 FUNC    GLOBAL DEFAULT  UND connect

     4: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_create

     5: 00000000     0 FUNC    GLOBAL DEFAULT  UND snprintf

     6: 00000000     0 FUNC    GLOBAL DEFAULT  UND usleep

     7: 00000000     0 FUNC    GLOBAL DEFAULT  UND memcpy

     8: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_equal

     9: 00000000     0 FUNC    WEAK   DEFAULT  UND \_\_cxa_finalize

    10: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc

    11: 00000000     0 FUNC    GLOBAL DEFAULT  UND socket

    12: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_detach

    13: 00000000     0 FUNC    GLOBAL DEFAULT  UND send

    14: 00000000     0 FUNC    GLOBAL DEFAULT  UND accept

    15: 00000000     0 FUNC    GLOBAL DEFAULT  UND write

    16: 00000000     0 FUNC    GLOBAL DEFAULT  UND fstat

    17: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_cond_broadcast

    18: 00000000     0 NOTYPE  WEAK   DEFAULT  UND \_\_deregister_frame_info

    19: 00000000     0 FUNC    GLOBAL DEFAULT  UND setsockopt

    20: 00000000     0 NOTYPE  WEAK   DEFAULT  UND \_ITM_registerTMCloneTable

    21: 00000000     0 FUNC    GLOBAL DEFAULT  UND read

    22: 00000000     0 NOTYPE  WEAK   DEFAULT  UND \_ITM_deregisterTMCloneTable

    23: 00000000     0 FUNC    GLOBAL DEFAULT  UND memset

    24: 00000000     0 FUNC    GLOBAL DEFAULT  UND poll

    25: 00000000     0 FUNC    GLOBAL DEFAULT  UND shutdown

    26: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_mutex_unlock

    27: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_self

    28: 00000000     0 FUNC    GLOBAL DEFAULT  UND getsockopt

    29: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_mutex_destroy

    30: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_mutex_lock

    31: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_cond_wait

    32: 00000000     0 FUNC    GLOBAL DEFAULT  UND \_\_errno_location

    33: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_mutex_init

    34: 00000000     0 FUNC    GLOBAL DEFAULT  UND strlen

    35: 00000000     0 FUNC    GLOBAL DEFAULT  UND open

    36: 00000000     0 FUNC    GLOBAL DEFAULT  UND fcntl

    37: 00000000     0 NOTYPE  WEAK   DEFAULT  UND \_\_register_frame_info

    38: 00000000     0 FUNC    GLOBAL DEFAULT  UND close

    39: 00000000     0 FUNC    GLOBAL DEFAULT  UND raise

    40: 00000000     0 FUNC    GLOBAL DEFAULT  UND free

    42: 00003540  1968 FUNC    GLOBAL DEFAULT    9 shim_session_setup

    43: 00003cf0   280 FUNC    GLOBAL DEFAULT    9 shim_session_teardown

    44: 00003e08    36 FUNC    GLOBAL DEFAULT    9 shim_session_finalize

    45: 000026cc   916 FUNC    GLOBAL DEFAULT    9 shim_screen_http_send

    46: 000010cc  1436 FUNC    GLOBAL DEFAULT    9 shim_screen_ensure_stream

     0: 00000000     0 NOTYPE  LOCAL  DEFAULT  UND 

    63: 00001668  1012 FUNC    LOCAL  DEFAULT    9 shim_screen_response

   171: 00003cf0   280 FUNC    GLOBAL DEFAULT    9 shim_session_teardown

   172: 00000000     0 FUNC    GLOBAL DEFAULT  UND connect

   173: 00003e08    36 FUNC    GLOBAL DEFAULT    9 shim_session_finalize

   174: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_create

   175: 00000000     0 FUNC    GLOBAL DEFAULT  UND snprintf

   176: 00000000     0 FUNC    GLOBAL DEFAULT  UND usleep

   177: 00000000     0 FUNC    GLOBAL DEFAULT  UND memcpy

   178: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_equal

   179: 00000000     0 FUNC    WEAK   DEFAULT  UND \_\_cxa_finalize

   180: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc

   181: 00000000     0 FUNC    GLOBAL DEFAULT  UND socket

   182: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_detach

   183: 00000000     0 FUNC    GLOBAL DEFAULT  UND send

   185: 00000000     0 FUNC    GLOBAL DEFAULT  UND accept

   186: 000026cc   916 FUNC    GLOBAL DEFAULT    9 shim_screen_http_send

   187: 00000000     0 FUNC    GLOBAL DEFAULT  UND write

   188: 00003540  1968 FUNC    GLOBAL DEFAULT    9 shim_session_setup

   189: 00000000     0 FUNC    GLOBAL DEFAULT  UND fstat

   190: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_cond_broadcast

   191: 00000000     0 NOTYPE  WEAK   DEFAULT  UND \_\_deregister_frame_info

   192: 00000000     0 FUNC    GLOBAL DEFAULT  UND setsockopt

   193: 00000000     0 NOTYPE  WEAK   DEFAULT  UND \_ITM_registerTMCloneTable

   194: 00000000     0 FUNC    GLOBAL DEFAULT  UND read

   195: 000010cc  1436 FUNC    GLOBAL DEFAULT    9 shim_screen_ensure_stream

   196: 00000000     0 NOTYPE  WEAK   DEFAULT  UND \_ITM_deregisterTMCloneTable

   197: 00000000     0 FUNC    GLOBAL DEFAULT  UND memset

   198: 00000000     0 FUNC    GLOBAL DEFAULT  UND poll

   199: 00000000     0 FUNC    GLOBAL DEFAULT  UND shutdown

   200: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_mutex_unlock

   202: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_self

   203: 00000000     0 FUNC    GLOBAL DEFAULT  UND getsockopt

   204: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_mutex_destroy

   205: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_mutex_lock

   206: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_cond_wait

   207: 00000000     0 FUNC    GLOBAL DEFAULT  UND \_\_errno_location

   208: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_mutex_init

   209: 00000000     0 FUNC    GLOBAL DEFAULT  UND strlen

   210: 00000000     0 FUNC    GLOBAL DEFAULT  UND open

   211: 00000000     0 FUNC    GLOBAL DEFAULT  UND fcntl

   212: 00000000     0 NOTYPE  WEAK   DEFAULT  UND \_\_register_frame_info

   213: 00000000     0 FUNC    GLOBAL DEFAULT  UND close

   214: 00000000     0 FUNC    GLOBAL DEFAULT  UND raise

   215: 00000000     0 FUNC    GLOBAL DEFAULT  UND free

PASS: STEP142 ISOLATED ARM/uClibc ELF AUDIT COMPLETED

No firmware tar, device upload, flash, or persistent patched executable created.

PASS: Step142 audit report saved: /Users/wademacintosh/Desktop/AK3918_step142_isolated_elf_audit.txt

BLOCKED FOR FLASH: a green static ELF audit does not prove device runtime or recovery.

wademacintosh\@Wades-MacBook-Air AK3918_GitHub % 