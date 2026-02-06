# Copyright 2024-2025 Amiable Development
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Chatbot integration module for Luminescent Cluster.

This module provides platform adapters for chat platforms (Discord, Slack,
Telegram, WhatsApp) with a unified interface for message handling.

See ADR-006: Chatbot Platform Integrations for design rationale.

Usage:
    from luminescent_cluster.chatbot.adapters import DiscordAdapter, SlackAdapter
    from luminescent_cluster.chatbot.gateway import ChatbotGateway

    # Create adapters
    discord = DiscordAdapter(config)
    slack = SlackAdapter(config)

    # Register with gateway
    gateway = ChatbotGateway()
    gateway.register_adapter(discord)
    gateway.register_adapter(slack)

    # Start processing messages
    await gateway.start()
"""

from .adapters.base import (
    BasePlatformAdapter,
    ChatMessage,
    MessageAuthor,
    AdapterConfig,
    ConnectionState,
)

__all__ = [
    "BasePlatformAdapter",
    "ChatMessage",
    "MessageAuthor",
    "AdapterConfig",
    "ConnectionState",
]
