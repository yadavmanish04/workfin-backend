from django.contrib import admin
from django.utils.html import format_html
from apps.ranking.models import RankingConfig, CandidateRank, RankingHistory, PointsCreditMapping
from apps.ranking.services import recalculate_all_ranks


@admin.register(PointsCreditMapping)
class PointsCreditMappingAdmin(admin.ModelAdmin):
    list_display = ['points_threshold', 'credits_required', 'is_active', 'updated_at']
    list_filter = ['is_active']
    list_editable = ['credits_required', 'is_active']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['points_threshold']

    fieldsets = (
        ('Mapping Configuration', {
            'fields': ('points_threshold', 'credits_required', 'is_active'),
            'description': 'Define how many credits are required for candidates with specific point thresholds. '
                          'Candidates will get credits based on the highest threshold they meet. '
                          'Example: If a candidate has 25 points and mappings exist for 0, 10, 20, 30 points, '
                          'they will get credits from the 20 points tier.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Recalculate all ranks when mapping changes
        count = recalculate_all_ranks()
        self.message_user(request, f'Points-Credits mapping saved. Recalculated ranks for {count} candidates.', level='success')


@admin.register(RankingConfig)
class RankingConfigAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'is_active', 'updated_at']
    list_filter = ['is_active']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Experience Points (Max 20)', {
            'fields': ('experience_points_per_year', 'max_experience_points'),
            'description': 'Configure points for years of experience'
        }),
        ('Education Points (Max 20)', {
            'fields': ('points_10th', 'points_12th', 'points_diploma', 'points_bachelors', 'points_masters', 'points_phd'),
            'description': 'Points awarded for highest degree (only one counts)'
        }),
        ('Certification Points (Max 20)', {
            'fields': ('points_per_certification', 'max_certification_points'),
            'description': 'Points per certification, with a maximum cap'
        }),
        ('Skills Points (Max 10)', {
            'fields': ('points_per_skill', 'max_skills_points'),
            'description': 'Points per skill listed, with a maximum cap'
        }),
        ('Profile Completeness Points (Max 20)', {
            'fields': ('points_resume_uploaded', 'points_video_uploaded', 'points_profile_image_uploaded',
                      'points_career_objective_filled', 'points_all_steps_completed'),
            'description': 'Bonus points for complete profile'
        }),
        ('Availability Bonus (Max 6)', {
            'fields': ('points_immediate_joining', 'points_willing_to_relocate'),
            'description': 'Bonus for candidate availability'
        }),
        ('Verification Bonus (Max 10)', {
            'fields': ('points_verified_profile',),
            'description': 'Bonus for admin-verified profiles'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.is_active:
            # Recalculate all ranks when config changes
            count = recalculate_all_ranks()
            self.message_user(request, f'Configuration saved. Recalculated ranks for {count} candidates.', level='success')


@admin.register(CandidateRank)
class CandidateRankAdmin(admin.ModelAdmin):
    list_display = ['candidate_link', 'total_score', 'credits_required', 'last_calculated']
    list_filter = ['last_calculated']
    search_fields = ['candidate__first_name', 'candidate__last_name', 'candidate__masked_name', 'candidate__user__email']
    readonly_fields = [
        'candidate', 'total_score', 'experience_score', 'education_score',
        'certification_score', 'skills_score', 'profile_completeness_score',
        'availability_score', 'verification_score', 'credits_required', 'last_calculated'
    ]
    ordering = ['-total_score']
    actions = ['recalculate_selected_ranks']

    fieldsets = (
        ('Candidate', {
            'fields': ('candidate',)
        }),
        ('Score Summary', {
            'fields': ('total_score', 'credits_required'),
        }),
        ('Score Breakdown', {
            'fields': (
                'experience_score',
                'education_score',
                'certification_score',
                'skills_score',
                'profile_completeness_score',
                'availability_score',
                'verification_score'
            ),
            'description': 'Detailed breakdown of score components'
        }),
        ('Metadata', {
            'fields': ('last_calculated',),
        })
    )

    def candidate_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('admin:candidates_candidate_change', args=[obj.candidate.id])
        return format_html('<a href="{}">{}</a>', url, obj.candidate.masked_name)
    candidate_link.short_description = 'Candidate'

    def recalculate_selected_ranks(self, request, queryset):
        from apps.ranking.services import update_candidate_rank
        count = 0
        for rank in queryset:
            update_candidate_rank(rank.candidate, save_history=True)
            count += 1
        self.message_user(request, f'Recalculated ranks for {count} candidate(s).', level='success')
    recalculate_selected_ranks.short_description = '🔄 Recalculate selected ranks'

    def has_add_permission(self, request):
        # Ranks are created automatically via signals
        return False


@admin.register(RankingHistory)
class RankingHistoryAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'total_score', 'credits_required', 'calculated_at']
    list_filter = ['calculated_at']
    search_fields = ['candidate__first_name', 'candidate__last_name', 'candidate__masked_name']
    readonly_fields = ['candidate', 'total_score', 'credits_required', 'calculated_at']
    ordering = ['-calculated_at']
    date_hierarchy = 'calculated_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
