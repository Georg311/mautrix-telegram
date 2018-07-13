# -*- coding: future_fstrings -*-
# mautrix-telegram - A Matrix-Telegram puppeting bridge
# Copyright (C) 2018 Tulir Asokan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from abc import abstractmethod
import abc
import asyncio
import logging

from telethon.errors import *

from mautrix_telegram.commands.auth import enter_password
from mautrix_telegram.util import format_duration


class AuthAPI(abc.ABC):
    log = logging.getLogger("mau.public.auth")

    def __init__(self, loop):
        self.loop = loop

    @abstractmethod
    def get_login_response(self, status=200, state="", username="", mxid="", message="", error="",
                           errcode=""):
        raise NotImplementedError()

    async def post_login_phone(self, user, phone):
        try:
            await user.client.sign_in(phone or "+123")
            return self.get_login_response(mxid=user.mxid, state="code", status=200,
                                           message="Code requested successfully.")
        except PhoneNumberInvalidError:
            return self.get_login_response(mxid=user.mxid, state="request", status=400,
                                           errcode="phone_number_invalid",
                                           error="Invalid phone number.")
        except PhoneNumberBannedError:
            return self.get_login_response(mxid=user.mxid, state="request", status=403,
                                           errcode="phone_number_banned",
                                           error="Your phone number is banned from Telegram.")
        except PhoneNumberAppSignupForbiddenError:
            return self.get_login_response(mxid=user.mxid, state="request", status=403,
                                           errcode="phone_number_app_signup_forbidden",
                                           error="You have disabled 3rd party apps on your account.")
        except PhoneNumberUnoccupiedError:
            return self.get_login_response(mxid=user.mxid, state="request", status=404,
                                           errcode="phone_number_unoccupied",
                                           error="That phone number has not been registered.")
        except PhoneNumberFloodError:
            return self.get_login_response(
                mxid=user.mxid, state="request", status=429, errcode="phone_number_flood",
                error="Your phone number has been temporarily blocked for flooding. "
                      "The ban is usually applied for around a day.")
        except FloodWaitError as e:
            return self.get_login_response(
                mxid=user.mxid, state="request", status=429, errcode="flood_wait",
                error="Your phone number has been temporarily blocked for flooding. "
                      f"Please wait for {format_duration(e.seconds)} before trying again.")
        except Exception:
            self.log.exception("Error requesting phone code")
            return self.get_login_response(mxid=user.mxid, state="request", status=500,
                                           errcode="exception",
                                           error="Internal server error while requesting code.")

    async def post_login_token(self, user, token):
        try:
            user_info = await user.client.sign_in(bot_token=token)
            asyncio.ensure_future(user.post_login(user_info), loop=self.loop)
            if user.command_status and user.command_status["action"] == "Login":
                user.command_status = None
            return self.get_login_response(mxid=user.mxid, state="logged-in", status=200,
                                           username=user_info.username)
        except AccessTokenInvalidError:
            return self.get_login_response(mxid=user.mxid, state="token", status=401,
                                           errcode="bot_token_invalid",
                                           error="Bot token invalid.")
        except AccessTokenExpiredError:
            return self.get_login_response(mxid=user.mxid, state="token", status=403,
                                           errcode="bot_token_expired",
                                           error="Bot token expired.")
        except Exception:
            self.log.exception("Error sending bot token")
            return self.get_login_response(mxid=user.mxid, state="token", status=500,
                                           error="Internal server error while sending token.")

    async def post_login_code(self, user, code, password_in_data):
        try:
            user_info = await user.client.sign_in(code=code)
            asyncio.ensure_future(user.post_login(user_info), loop=self.loop)
            if user.command_status and user.command_status["action"] == "Login":
                user.command_status = None
            return self.get_login_response(mxid=user.mxid, state="logged-in", status=200,
                                           username=user_info.username)
        except PhoneCodeInvalidError:
            return self.get_login_response(mxid=user.mxid, state="code", status=401,
                                           errcode="phone_code_invalid",
                                           error="Incorrect phone code.")
        except PhoneCodeExpiredError:
            return self.get_login_response(mxid=user.mxid, state="code", status=403,
                                           errcode="phone_code_expired",
                                           error="Phone code expired.")
        except SessionPasswordNeededError:
            if not password_in_data:
                if user.command_status and user.command_status["action"] == "Login":
                    user.command_status = {
                        "next": enter_password,
                        "action": "Login (password entry)",
                    }
                return self.get_login_response(
                    mxid=user.mxid, state="password", status=202,
                    message="Code accepted, but you have 2-factor authentication is enabled.")
            return None
        except Exception:
            self.log.exception("Error sending phone code")
            return self.get_login_response(mxid=user.mxid, state="code", status=500,
                                           errcode="exception",
                                           error="Internal server error while sending code.")

    async def post_login_password(self, user, password):
        try:
            user_info = await user.client.sign_in(password=password)
            asyncio.ensure_future(user.post_login(user_info), loop=self.loop)
            if user.command_status and user.command_status["action"] == "Login (password entry)":
                user.command_status = None
            return self.get_login_response(mxid=user.mxid, state="logged-in", status=200,
                                           username=user_info.username)
        except PasswordEmptyError:
            return self.get_login_response(mxid=user.mxid, state="password", status=400,
                                           errcode="password_empty",
                                           error="Empty password.")
        except PasswordHashInvalidError:
            return self.get_login_response(mxid=user.mxid, state="password", status=401,
                                           errcode="password_invalid",
                                           error="Incorrect password.")
        except Exception:
            self.log.exception("Error sending password")
            return self.get_login_response(mxid=user.mxid, state="password", status=500,
                                           errcode="exception",
                                           error="Internal server error while sending password.")
