"""Import every model so Base.metadata is complete for Alembic autogenerate
and so string-based relationship() forward refs resolve at mapper
configuration time."""

from app.db.base import Base  # noqa: F401
from app.models.admin_audit import AdminAuditLog  # noqa: F401
from app.models.admitad_feed import AdmitadFeedItem  # noqa: F401
from app.models.app_setting import AppSetting  # noqa: F401
from app.models.affiliate import AffiliateClick  # noqa: F401
from app.models.analytics import PageView  # noqa: F401
from app.models.affiliate_network import AffiliateNetwork  # noqa: F401
from app.models.ai_usage import AIUsage  # noqa: F401
from app.models.credit import CreditPackage, CreditTransaction  # noqa: F401
from app.models.developer import DeveloperAccount, DeveloperApiKey, DeveloperCreditPack, DeveloperTryOn  # noqa: F401
from app.models.fashn_ledger import FashnCreditLedger, FashnLiveAuthorization  # noqa: F401
from app.models.history import ProductView, SearchHistory  # noqa: F401
from app.models.outfit import Outfit, OutfitItem, SavedLook  # noqa: F401
from app.models.photo import UserPhoto  # noqa: F401
from app.models.preference import UserPreference  # noqa: F401
from app.models.product import Product, ProductImage  # noqa: F401
from app.models.saved_product import SavedProduct  # noqa: F401
from app.models.community import (  # noqa: F401
    Challenge,
    ChallengeWinner,
    CommentLike,
    CommunityPost,
    CommunityReport,
    Follow,
    MusicTrack,
    PollVote,
    PostComment,
    PostLike,
    SavedPost,
)
from app.models.notification import Announcement, Notification, PushSubscription  # noqa: F401
from app.models.visual_search import VisualSearch  # noqa: F401
from app.models.price_watch import PriceWatch  # noqa: F401
from app.models.contact import ContactMessage  # noqa: F401
from app.models.admin_email import AdminEmail, EmailSendDay  # noqa: F401
from app.models.extension import ExtensionToken  # noqa: F401
from app.models.ready_look import ReadyLook, ReadyLookItem  # noqa: F401
from app.models.referral import Referral, ReferralCode  # noqa: F401
from app.models.shared_look import SharedLook  # noqa: F401
from app.models.store import Store, StorePlan, StoreProduct, StoreProductView  # noqa: F401
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
