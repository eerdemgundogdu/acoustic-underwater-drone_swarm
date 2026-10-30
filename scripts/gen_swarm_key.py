"""Suru icin rastgele 128 bit SipHash anahtari uretir ve PlatformIO build_flags
satirini yazdirir. Ayni surudeki butun dugumler ayni anahtarla derlenir.

    python3 scripts/gen_swarm_key.py
"""

import secrets


def main():
    key = secrets.token_bytes(16)
    flag = ','.join(f'0x{b:02X}' for b in key)
    print('platformio.ini [env:node] build_flags satirina ekleyin:')
    print(f'    -D SWARM_KEY_BYTES={flag}')


if __name__ == '__main__':
    main()
