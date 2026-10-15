"""Research assistant page package.

The research assistant is a guided workspace composed of ten sections.
Each section is a real widget that participates in the page's
navigation contract; navigation preserves the work in every section.
"""

from academic_platform.ui.pages.research_assistant.assistant_page import (
    ResearchAssistantPage,
)
from academic_platform.ui.pages.research_assistant.section_base import (
    AssistantSection,
    AssistantSectionId,
)
from academic_platform.ui.pages.research_assistant.section_host import (
    SectionHost,
)
from academic_platform.ui.pages.research_assistant.sections import (
    create_section,
)

__all__ = [
    "AssistantSection",
    "AssistantSectionId",
    "ResearchAssistantPage",
    "SectionHost",
    "create_section",
]