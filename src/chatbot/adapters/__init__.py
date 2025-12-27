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
Platform adapters for Luminescent Cluster chatbot.

Each adapter implements the BasePlatformAdapter protocol for its platform.
"""

from .base import (
    BasePlatformAdapter,
    ChatMessage,
    MessageAuthor,
    AdapterConfig,
    ConnectionState,
    normalize_mentions,
)

__all__ = [
    "BasePlatformAdapter",
    "ChatMessage",
    "MessageAuthor",
    "AdapterConfig",
    "ConnectionState",
    "normalize_mentions",
]
