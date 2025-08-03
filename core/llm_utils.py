import json
import structlog
from pydantic import BaseModel, ValidationError, model_validator
from typing import Literal, Optional

log = structlog.get_logger(__name__)


class BuyerReply(BaseModel):
    """Pydantic model for buyer LLM responses with enhanced reasoning."""

    action: Literal["accept", "counter_offer"]
    price: Optional[float] = None
    reason: Optional[str] = None  # Add reasoning field to match seller

    @model_validator(mode="after")
    def validate_price_with_action(self):
        if self.action == "counter_offer" and self.price is None:
            raise ValueError("Price is required when action is counter_offer")
        if self.action == "accept" and self.price is not None:
            raise ValueError("Price should be null when action is accept")
        return self


class SellerReply(BaseModel):
    action: Literal["accept", "counter_offer", "reject"]
    price: Optional[float] = None
    reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_price_required_for_counter_offer(self):
        if self.action == "counter_offer" and self.price is None:
            raise ValueError("price is required when action is counter_offer")
        return self


async def call_llm_with_retry(messages, model_cls, llm, max_retries=2):
    """Call LLM with automatic retry on validation failure."""
    log.info("llm.request_start", model_cls=model_cls.__name__, max_retries=max_retries)

    for attempt in range(max_retries + 1):
        try:
            log.debug("llm.request_attempt", attempt=attempt + 1)
            response = await llm.ainvoke(messages)
            content = response.content.strip()
            log.debug("llm.response_raw", content=content[:100])

            # Try parsing as JSON first
            try:
                result = model_cls.model_validate_json(content)
                log.info(
                    "llm.request_success",
                    model_cls=model_cls.__name__,
                    attempt=attempt + 1,
                    result=(
                        result.model_dump()
                        if hasattr(result, "model_dump")
                        else str(result)
                    ),
                )
                return result
            except (ValidationError, json.JSONDecodeError) as e:
                log.warning("llm.parse_error", error=str(e), content=content)
                # For backward compatibility, handle simple number responses for SellerReply
                if model_cls == SellerReply:
                    try:
                        price = float(content)
                        result = SellerReply(action="counter_offer", price=price)
                        log.info(
                            "llm.request_success_fallback_parse",
                            model_cls=model_cls.__name__,
                            attempt=attempt + 1,
                            result=result.model_dump(),
                        )
                        return result
                    except (ValueError, TypeError):
                        pass
                raise

        except Exception as e:
            log.warning(
                "llm.request_attempt_failed",
                attempt=attempt + 1,
                error=str(e),
                error_type=type(e).__name__,
            )
            if attempt < max_retries:
                # Add validation instruction and retry
                messages.append(
                    {"role": "user", "content": "Respond ONLY in valid JSON per schema"}
                )
                continue
            else:
                log.error(
                    "llm.request_failed_all_retries",
                    max_retries=max_retries,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
