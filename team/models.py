from django.db import models

class TeamMember(models.Model):
    """Stores data for an individual member of the JH Motiv team."""
    
    # 1. DEFINE THE RPG CLASSES
    CLASS_CHOICES = [
        ('GAME_MASTER', 'Game Master (Founder/Jack of All Trades)'), # The Boss Class
        ('PALADIN', 'Paladin (Leader/Tank)'),
        ('ROGUE', 'Rogue (Agility/Sales)'),
        ('MAGE', 'Mage (Specialist/Strategy)'),
        ('BARD', 'Bard (Community/Marketing)'),
        ('HEALER', 'Healer (Coach/Support)'),
        ('WARRIOR', 'Warrior (Operations/Grind)'),
        ('TECHNOMANCER', 'Technomancer (Dev/Tech)'),
        ('NPC', 'NPC (Guest/Other)'),
    ]

    # Core Data
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=150, help_text="Job title (e.g., Founder, Lead Coach).")
    
    # --- NEW FIELD ---
    character_class = models.CharField(
        max_length=50, 
        choices=CLASS_CHOICES, 
        default='WARRIOR',
        help_text="Determines the color ring and icon on the About page."
    )
    # -----------------

    bio = models.TextField(help_text="A brief description or biography.")
    
    # Image & Display
    profile_image = models.ImageField(
        upload_to='team_photos/', 
        help_text="Upload a professional photo for the team member."
    )
    is_active = models.BooleanField(default=True, help_text="Display on the Meet the Team page.")
    order = models.PositiveIntegerField(default=0, help_text="Manual ordering for display.")

    # 2. COLOR LOGIC (Tailwind Classes)
    @property
    def css_color_class(self):
        colors = {
            'GAME_MASTER': 'slate-900',   # Onyx/Black
            'PALADIN': 'yellow-500',      # Gold
            'ROGUE': 'green-600',         # Poison Green
            'MAGE': 'indigo-500',         # Arcane Blue/Purple
            'BARD': 'pink-500',           # Charisma Pink
            'HEALER': 'teal-400',         # Life Teal
            'WARRIOR': 'red-600',         # Aggro Red
            'TECHNOMANCER': 'cyan-400',   # Cyber Blue
            'NPC': 'gray-400',            # Neutral Gray
        }
        return colors.get(self.character_class, 'gray-400')

    # 3. ICON LOGIC (Emojis)
    @property
    def class_icon(self):
        icons = {
            'GAME_MASTER': '🎲', 
            'PALADIN': '🛡️',
            'ROGUE': '🗡️',
            'MAGE': '🔮',
            'BARD': '🎵',
            'HEALER': '💖',
            'WARRIOR': '⚔️',
            'TECHNOMANCER': '💾',
            'NPC': '👤',
        }
        return icons.get(self.character_class, '👤')

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Team Member"
        verbose_name_plural = "Team Members"

    def __str__(self):
        return f"{self.name} ({self.get_character_class_display()})"