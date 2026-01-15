from django.db import models
from products.models import Variant

class FunnelTier(models.Model):
    """
    Represents a pricing tier specifically for the Awakening funnel.
    e.g. 'LONE WOLF', 'GUILD MEMBER', etc.
    """
    name = models.CharField(max_length=100, help_text="Display name e.g. 'GUILD MEMBER'")
    slug = models.SlugField(max_length=100, help_text="Used for HTML IDs, e.g. 'guild_member'")
    
    # Link to the actual product variant being sold
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name='funnel_tiers')
    quantity = models.PositiveIntegerField(default=1, help_text="How many units of the variant are included?")
    
    # Visuals
    css_class = models.CharField(
        max_length=50, 
        help_text="CSS class for styling hooks, e.g. 'LONE_WOLF', 'RAID_LEADER'",
        default="LONE_WOLF"
    )
    order = models.PositiveIntegerField(default=0, help_text="Order in which tiers appear (lowest first)")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} (Qty: {self.quantity})"

    @property
    def total_price(self):
        """Calculates total price based on variant price * quantity."""
        if self.variant:
            return self.variant.price * self.quantity
        return 0


class TierPerk(models.Model):
    """
    Bullet points (perks) listed under a specific tier.
    """
    tier = models.ForeignKey(FunnelTier, on_delete=models.CASCADE, related_name='perks')
    text = models.CharField(max_length=255, help_text="The perk text, e.g. 'Signed & Numbered'")
    link_url = models.URLField(
        blank=True,
        null=True,
        help_text="Optional: A URL for this perk, e.g., a link to a WhatsApp group."
    )
    linked_offering = models.ForeignKey(
        'coaching_core.Offering',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="Optional: Link this perk to a specific coaching offering to grant access."
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text


class OrderBump(models.Model):
    """
    Represents a final upsell/cross-sell offer presented at checkout.
    e.g., "Add the Audiobook" vs "Add the Digital Toolkit".
    """
    name = models.CharField(max_length=100, help_text="Internal name for this offer, e.g., 'Audiobook Bump'")
    headline = models.CharField(max_length=255, help_text="The catchy headline above the choice, e.g., 'Final Offer: Upgrade Your Order!'")
    
    # The product variant this bump offer adds to the cart
    variant = models.ForeignKey(
        'products.Variant',
        on_delete=models.CASCADE,
        help_text="The product variant that will be added to the order."
    )
    
    is_default_choice = models.BooleanField(
        default=False,
        help_text="Check this for the offer you want to be pre-selected by default."
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (Adds: {self.variant.name})"