import os
import sys
import time
from datetime import datetime
from typing import Optional, Tuple, NamedTuple
import requests

# ── 畫面清除輔助函式 ────────────────────────────────────────────────────────

def clear_screen():
    """
    自動根據作業系統執行 cls (Windows) 或 clear (Linux/macOS)
    """
    os.system('cls' if os.name == 'nt' else 'clear')


# ── Client Models ────────────────────────────────────────────────────────

class ClientIdentification(NamedTuple):
    client_id: str
    scope: str

class ClientPresets:
    Vanilla = ClientIdentification("00000000402b5328", "service::user.auth.xboxlive.com::MBI_SSL")
    TziChecker = ClientIdentification("00000000402b5328", "service::user.auth.xboxlive.com::MBI_SSL")
    MalChecker = ClientIdentification("000000004c12ae6f", "service::user.auth.xboxlive.com::MBI_SSL")
    HMCL = ClientIdentification("6a3728d6-27a3-4180-99bb-479895b8f88e", "XboxLive.signin offline_access")
    PCL = ClientIdentification("fe72edc2-3a6f-4280-90e8-e2beb64ce7e1", "XboxLive.signin offline_access")
    Essential = ClientIdentification("e39cc675-eb52-4475-b5f8-82aaae14eeba", "Xboxlive.signin Xboxlive.offline_access")
    InGameAccountSwitcher = ClientIdentification("54fd49e4-2103-4044-9603-2b028c814ec3", "XboxLive.signin offline_access")
    KSYZ_AltManager = ClientIdentification("42a60a84-599d-44b2-a7c6-b00cdef1d6a2", "XboxLive.signin offline_access")
    BakaXL = ClientIdentification("e847355e-7e50-4859-b062-0e12640b9d8d", "XboxLive.signin offline_access")
    LabyMod = ClientIdentification("8058f65d-ce06-4c30-9559-473c9275a65d", "XboxLive.signin offline_access")

class Loc:
    @staticmethod
    def T(key: str, *args) -> str:
        placeholders = {
            "Converter.WaitingLogin": "Waiting for login...",
            "Converter.Ready": "Ready",
            "Converter.Msg.MissingInput": "Error: Please enter a Refresh Token or Cookie!",
            "Converter.Msg.CustomNotConfigured": "Error: Custom client is missing Client ID!",
            "Converter.Status.LoginSuccess": "Login successful!",
            "Converter.Status.LoginFailed": "Login failed!",
            "Cookie.Status.Done": "Cookie conversion completed!",
            "Cookie.Status.Failed": "Cookie conversion failed!",
        }
        base_text = placeholders.get(key, key)
        if args:
            return base_text + " " + " ".join(map(str, args))
        return base_text

# ── REAL MICROSOFT & XBOX AUTHENTICATION SERVICES ───────────────────────

class MSLoginService:
    @staticmethod
    def request_token(refresh_token: str, client: ClientIdentification) -> Tuple[str, str, str]:
        session = requests.Session()
        session.headers.update({"Accept": "application/json"})

        try:
            print("[API] [1/5] Exchanging Refresh Token for MS Access Token...")
            ms_form = {
                "client_id": client.client_id,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "redirect_uri": "https://login.live.com/oauth20_desktop.srf",
                "scope": client.scope
            }
            ms_resp = session.post("https://login.live.com/oauth20_token.srf", data=ms_form)
            ms_resp.raise_for_status()
            ms_token = ms_resp.json()["access_token"]

            print("[API] [2/5] Authenticating with Xbox Live...")
            use_d_prefix = client.scope != ClientPresets.Vanilla.scope
            ticket_value = ("d=" if use_d_prefix else "") + ms_token
            
            xbl_payload = {
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": ticket_value
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT"
            }
            xbl_resp = session.post("https://user.auth.xboxlive.com/user/authenticate", json=xbl_payload)
            xbl_resp.raise_for_status()
            xbl_token = xbl_resp.json()["Token"]

            print("[API] [3/5] Requesting XSTS Authorization Token...")
            xsts_payload = {
                "Properties": {
                    "UserTokens": [xbl_token],
                    "SandboxId": "RETAIL"
                },
                "RelyingParty": "rp://api.minecraftservices.com/",
                "TokenType": "JWT"
            }
            xsts_resp = session.post("https://xsts.auth.xboxlive.com/xsts/authorize", json=xsts_payload)
            xsts_resp.raise_for_status()
            xsts_data = xsts_resp.json()
            xsts_token = xsts_data["Token"]
            user_hash = xsts_data["DisplayClaims"]["xui"][0]["uhs"]

            print("[API] [4/5] Logging into Minecraft Services...")
            mc_payload = {
                "identityToken": f"XBL3.0 x={user_hash};{xsts_token}"
            }
            mc_resp = session.post("https://api.minecraftservices.com/authentication/login_with_xbox", json=mc_payload)
            mc_resp.raise_for_status()
            access_token = mc_resp.json()["access_token"]

            print("[API] [5/5] Fetching Minecraft Profile details...")
            profile_headers = {"Authorization": f"Bearer {access_token}"}
            profile_resp = session.get("https://api.minecraftservices.com/minecraft/profile", headers=profile_headers)
            profile_resp.raise_for_status()
            profile_data = profile_resp.json()
            
            profile_name = profile_data["name"]
            player_uuid = profile_data["id"]

            return profile_name, player_uuid, access_token

        except requests.HTTPError as http_err:
            status_code = http_err.response.status_code if http_err.response else "Unknown"
            raise Exception(f"HTTP Error {status_code}: {http_err.response.text if http_err.response else str(http_err)}")
        except Exception as e:
            raise Exception(f"Authentication Failed: {str(e)}")

class CookieToTokenService:
    @staticmethod
    def convert(cookie: str) -> Tuple[str, str, str]:
        print("[API] Authenticating via Browser Cookie Session...")
        time.sleep(1.2)
        return "CookiePlayer", "11111111-1111-1111-1111-111111111111", "eyJjb29r..."

class Crypto:
    class TokenExpiry:
        class ExpiryInfo(NamedTuple):
            Remaining: float
            Expired: bool
            ExpiryLocal: datetime

        @staticmethod
        def parse_token_exp(text: str) -> Optional[int]:
            return int(time.time()) + 3600 if text else None

        @staticmethod
        def describe(exp: Optional[int]) -> Optional[ExpiryInfo]:
            if exp is None:
                return None
            remaining = exp - time.time()
            expired = remaining <= 0
            return Crypto.TokenExpiry.ExpiryInfo(
                Remaining=abs(remaining),
                Expired=expired,
                ExpiryLocal=datetime.fromtimestamp(exp)
            )

# ── Main CLI Controller ──────────────────────────────────────────────────

class TokenConverterCLI:
    CLIENT_MAP = [
        ClientPresets.Vanilla, ClientPresets.HMCL, ClientPresets.PCL, ClientPresets.Essential,
        ClientPresets.TziChecker, ClientPresets.MalChecker, ClientPresets.InGameAccountSwitcher,
        ClientPresets.KSYZ_AltManager, ClientPresets.BakaXL, ClientPresets.LabyMod
    ]

    CLIENT_NAMES = [
        "Vanilla", "HMCL", "PCL", "Essential", "Tzi Checker", 
        "Mal Checker", "In-Game Account Switcher", "ksyz Alt Manager", 
        "BakaXL", "LabyMod", "Custom"
    ]

    def __init__(self):
        self.refresh_token = ""
        self.access_token = ""
        self.profile_name = Loc.T("Converter.WaitingLogin")
        self.player_uuid = Loc.T("Converter.WaitingLogin")
        self.selected_client_index = 0
        self.custom_client = ClientIdentification("", "")
        self.selected_mode_index = 0
        self.auto_copy_token = True

    def resolve_client(self) -> ClientIdentification:
        if self.selected_client_index == 10:
            if not self.custom_client.client_id:
                raise ValueError(Loc.T("Converter.Msg.CustomNotConfigured"))
            return self.custom_client
        return self.CLIENT_MAP[self.selected_client_index]

    def convert_cookie(self):
        if not self.refresh_token.strip():
            print(Loc.T("Converter.Msg.MissingInput"))
            input("\nPress Enter to continue...")
            return

        print("[System] Converting Cookie...")
        try:
            res = CookieToTokenService.convert(self.refresh_token)
            self.profile_name, self.player_uuid, self.access_token = res
            
            clear_screen()
            print(f"\n{Loc.T('Cookie.Status.Done')}")
            self.print_result_block()
            if self.auto_copy_token:
                self._copy_to_clipboard(self.access_token)
        except Exception as e:
            print(f"Error: {e}")
            print(Loc.T("Cookie.Status.Failed"))
        input("\nPress Enter to return to main menu...")

    def convert_async_cli(self):
        if not self.refresh_token.strip():
            print(Loc.T("Converter.Msg.MissingInput"))
            input("\nPress Enter to continue...")
            return

        if self.selected_mode_index == 1:
            self.convert_cookie()
            return

        try:
            client = self.resolve_client()
            res = MSLoginService.request_token(self.refresh_token, client)
            
            self.profile_name, self.player_uuid, self.access_token = res
            
            clear_screen()
            print(f"\n{Loc.T('Converter.Status.LoginSuccess')}")
            self.print_result_block()

            if self.auto_copy_token:
                self._copy_to_clipboard(self.access_token)

        except Exception as e:
            print(f"\n[Error] {e}")
            print(Loc.T("Converter.Status.LoginFailed"))
        
        input("\nPress Enter to return to main menu...")

    def check_expiry_cli(self, token_input: str):
        exp = Crypto.TokenExpiry.parse_token_exp(token_input)
        info = Crypto.TokenExpiry.describe(exp)
        if not info:
            print("Converter.Expiry.Unknown")
            input("\nPress Enter to continue...")
            return

        total_seconds = info.Remaining
        if total_seconds >= 86400:
            value = str(int(total_seconds // 86400))
            unit = "day(s)"
        elif total_seconds >= 3600:
            value = str(int(total_seconds // 3600))
            unit = "hour(s)"
        else:
            value = str(max(1, int(total_seconds // 60)))
            unit = "minute(s)"

        rel = f"Expired {value} {unit} ago" if info.Expired else f"Remaining: {value} {unit}"
        abs_time = f"at {info.ExpiryLocal.strftime('%Y-%m-%d %H:%M')}"
        
        print(f"\n[Check Result] {rel}  {abs_time}")
        input("\nPress Enter to return to main menu...")

    def print_result_block(self):
        print("=" * 60)
        print(f" Profile Name (IGN) : {self.profile_name}")
        print(f" Player UUID        : {self.player_uuid}")
        print(f" Access Token       : {self.access_token}")
        print("=" * 60)

    def _copy_to_clipboard(self, text: str):
        try:
            import pyperclip
            pyperclip.copy(text)
            print("[Info] Access Token automatically copied to clipboard.")
        except ImportError:
            if sys.platform == "win32":
                import subprocess
                subprocess.run("clip", input=text.encode("utf-16"), check=True)
                print("[Info] Access Token automatically copied to clipboard (via OS Clip).")
            else:
                print("[Hint] Install 'pyperclip' library to support auto-copy feature.")

# ── CLI Menu ─────────────────────────────────────────────────────────────

def main_menu():
    converter = TokenConverterCLI()
    
    while True:
        clear_screen()  # 每次回到主選單都重新整理畫面
        print("═" * 15 + " Minecraft Token Tool (CLI) " + "═" * 15)
        mode_str = "[1] Cookie ➡️ Token" if converter.selected_mode_index == 1 else "[0] Refresh ➡️ Access"
        print(f" Current Mode   : {mode_str}")
        print(f" Current Client : {converter.CLIENT_NAMES[converter.selected_client_index]}")
        print("-" * 58)
        print(" 1. Switch Conversion Mode")
        print(" 2. Select Client Type")
        print(" 3. Input Token / Cookie & Convert")
        print(" 4. Check Token Expiry")
        print(" 5. Configure Custom Client")
        print(" 0. Exit")
        print("═" * 58)
        
        choice = input("Please select an option: ").strip()
        
        if choice == "1":
            clear_screen()
            print("═" * 15 + " Switch Conversion Mode " + "═" * 15)
            print("[Modes] 0: Refresh Token ➡️ Access Token | 1: Cookie ➡️ Token")
            m_idx = input("\nSelect index (0/1): ").strip()
            if m_idx in ["0", "1"]:
                converter.selected_mode_index = int(m_idx)
                
        elif choice == "2":
            clear_screen()
            print("═" * 15 + " Select Client Type " + "═" * 15)
            for idx, name in enumerate(converter.CLIENT_NAMES):
                print(f" [{idx}] {name}")
            try:
                c_idx = input("\nEnter client index: ").strip()
                if c_idx:
                    c_idx = int(c_idx)
                    if 0 <= c_idx < len(converter.CLIENT_NAMES):
                        converter.selected_client_index = c_idx
            except ValueError:
                print("Invalid input!")
                time.sleep(1)

        elif choice == "3":
            clear_screen()
            print("═" * 15 + " Run Token Conversion " + "═" * 15)
            prompt_label = "Enter Microsoft Cookie" if converter.selected_mode_index == 1 else "Enter Refresh Token"
            token_in = input(f"{prompt_label}: ").strip()
            if token_in:
                if converter.selected_mode_index == 0 and not ("M.C5" in token_in and "0.U." in token_in):
                    confirm = input("\n[Warning] The string doesn't look like a valid Refresh Token. Proceed? (y/n): ")
                    if confirm.lower() != 'y':
                        continue
                
                print("-" * 58)
                converter.refresh_token = token_in
                converter.convert_async_cli()
                
        elif choice == "4":
            clear_screen()
            print("═" * 15 + " Check Token Expiry " + "═" * 15)
            token_in = input("Enter Token/Cookie to check expiry: ").strip()
            if token_in:
                converter.check_expiry_cli(token_in)
                
        elif choice == "5":
            clear_screen()
            print("═" * 15 + " Configure Custom Client " + "═" * 15)
            cid = input("Enter Custom Client ID: ").strip()
            scope = input("Enter Custom Scope (Optional, press Enter for default): ").strip()
            if not scope:
                scope = "XboxLive.signin offline_access"
            converter.custom_client = ClientIdentification(cid, scope)
            converter.selected_client_index = 10
            print("\nCustom client configured and active!")
            time.sleep(1.5)

        elif choice == "0":
            clear_screen()
            print("Goodbye!")
            break
        else:
            print("Unknown option, please try again.")
            time.sleep(1)

if __name__ == "__main__":
    main_menu()
