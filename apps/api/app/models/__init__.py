"""Import every model so Base.metadata is complete for Alembic autogenerate
and so string-based relationship() forward refs resolve at mapper
configuration time."""

from app.db.base import Base  # noqa: F401
from app.models.admin_audit import AdminAuditLog  # noqa: F401
from app.models.affiliate import AffiliateClick  # noqa: F401
from app.models.affiliate_network import AffiliateNetwork  # noqa: F401
from app.models.ai_usage import AIUsage  # noqa: F401
from app.models.credit import CreditPackage, CreditTransaction  # noqa: F401
from app.models.history import ProductView, SearchHistory  # noqa: F401
from app.models.outfit import Outfit, OutfitItem, SavedLook  # noqa: F401
from app.models.photo import UserPhoto  # noqa: F401
from app.models.preference import UserPreference  # noqa: F401
from app.models.product import Product, ProductImage  # noqa: F401
from app.models.retailer import ProductCategory, Retailer  # noqa: F401
from app.models.stylist import StylistRequest  # noqa: F401
from app.models.subscription import Payment, Subscription  # noqa: F401
from app.models.tryon import TryOnJob, TryOnResult  # noqa: F401
from app.models.user import EmailVerificationToken, PasswordResetToken, RefreshToken, User  # noqa: F401
from app.models.wardrobe import WardrobeItem  # noqa: F401

__all__ = [
    "Base",
    "User",
    "RefreshToken",
    "PasswordResetToken",
    "EmailVerificationToken",
    "UserPhoto",
    "UserPreference",
    "CreditTransaction",
    "CreditPackage",
    "Subscription",
    "Payment",
    "Retailer",
    "AffiliateNetwork",
    "ProductCategory",
    "Product",
    "ProductImage",
    "TryOnJob",
    "TryOnResult",
    "Outfit",
    "OutfitItem",
    "SavedLook",
    "AffiliateClick",
    "AIUsage",
    "StylistRequest",
    "SearchHistory",
    "ProductView",
    "WardrobeItem",
]
