from django.contrib import admin
from django import forms
from django.utils.functional import cached_property
from .models import *

FILTER_OPTIONS_PAGE_SIZE = 25

class WorkExperienceInline(admin.TabularInline):
    model = WorkExperience
    extra = 1
    fields = ['company_name', 'role_title', 'start_date', 'end_date', 'is_current', 'location','current_ctc', 'description']

class CareerGapInline(admin.TabularInline):
    model = CareerGap
    extra = 1
    fields = ['start_date', 'end_date', 'gap_reason']

class EducationInline(admin.TabularInline):
    model = Education
    extra = 1
    fields = ['institution_name', 'degree', 'field_of_study', 'start_year', 'end_year', 'is_ongoing', 'grade_percentage', 'location']

class CertificationInline(admin.TabularInline):
    model = Certification
    extra = 1
    fields = ['certification_name', 'issuing_organization', 'issue_date', 'document']

class FilterOptionInline(admin.TabularInline):
    model = FilterOption
    extra = 0
    fields = ['name', 'slug', 'parent', 'icon', 'display_order', 'is_active', 'is_approved', 'submitted_by', 'submitted_at']
    readonly_fields = ['submitted_by', 'submitted_at']
    can_delete = True

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        class PaginatedFormset(formset):
            def __init__(self_formset, *args, **kwargs):
                super().__init__(*args, **kwargs)
                page = int(request.GET.get('inline_page', 1))
                start = (page - 1) * FILTER_OPTIONS_PAGE_SIZE
                self_formset.queryset = self_formset.queryset[start:start + FILTER_OPTIONS_PAGE_SIZE]

        PaginatedFormset.max_num = FILTER_OPTIONS_PAGE_SIZE
        return PaginatedFormset

@admin.register(FilterCategory)
class FilterCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'display_order', 'is_active', 'option_count', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [FilterOptionInline]
    ordering = ['display_order', 'name']
    change_form_template = 'candidates/filter_category_change_form.html'

    def option_count(self, obj):
        return obj.options.count()
    option_count.short_description = 'Number of Options'

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            obj = self.get_object(request, object_id)
            if obj:
                import math
                total_count = obj.options.count()
                total_pages = max(1, math.ceil(total_count / FILTER_OPTIONS_PAGE_SIZE))
                current_page = int(request.GET.get('inline_page', 1))
                current_page = max(1, min(current_page, total_pages))
                extra_context['inline_pagination'] = {
                    'current_page': current_page,
                    'total_pages': total_pages,
                    'total_count': total_count,
                    'page_size': FILTER_OPTIONS_PAGE_SIZE,
                    'page_range': range(1, total_pages + 1),
                }
        return super().changeform_view(request, object_id, form_url, extra_context)


# Custom proxy model for pending locations
class PendingFilterOption(FilterOption):
    class Meta:
        proxy = True
        verbose_name = "Pending Location"
        verbose_name_plural = "📋 Pending Locations"


@admin.register(PendingFilterOption)
class PendingFilterOptionAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'parent_info', 'created_at', 'approve_button']
    list_filter = ['category', 'created_at']
    search_fields = ['name', 'slug']
    ordering = ['-created_at']
    raw_id_fields = ['parent']

    def parent_info(self, obj):
        return obj.parent.name if obj.parent else '-'
    parent_info.short_description = 'Parent'

    # Only show pending locations
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(is_active=False)
        return qs

    # Show approve button
    def approve_button(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<a class="button" href="#" onclick="approveLocation({}); return false;" style="background-color: #417690; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none;">✅ Approve</a>',
            obj.pk
        )
    approve_button.short_description = 'Action'
    approve_button.allow_tags = True

    actions = ['approve_locations', 'reject_locations']

    def approve_locations(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} location(s) approved successfully!', level='success')
    approve_locations.short_description = '✅ Approve selected locations'

    def reject_locations(self, request, queryset):
        count = queryset.delete()[0]
        self.message_user(request, f'{count} location(s) rejected and deleted.', level='warning')
    reject_locations.short_description = '❌ Reject and delete selected'

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        return ['name', 'category', 'parent', 'slug', 'created_at']


class CandidateAdminForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        try:
            # Filter role options to only show department category
            dept_category = FilterCategory.objects.get(slug='department')
            self.fields['role'].queryset = FilterOption.objects.filter(category=dept_category)
        except FilterCategory.DoesNotExist:
            pass
            
        try:
            # Filter religion options to only show religion category  
            religion_category = FilterCategory.objects.get(slug='religion')
            self.fields['religion'].queryset = FilterOption.objects.filter(category=religion_category)
        except FilterCategory.DoesNotExist:
            pass
            
        try:
            # Filter location options by their respective categories
            country_category = FilterCategory.objects.get(slug='country')
            state_category = FilterCategory.objects.get(slug='state') 
            city_category = FilterCategory.objects.get(slug='city')
            
            self.fields['country'].queryset = FilterOption.objects.filter(category=country_category)
            self.fields['state'].queryset = FilterOption.objects.filter(category=state_category)
            self.fields['city'].queryset = FilterOption.objects.filter(category=city_category)
        except FilterCategory.DoesNotExist:
            pass


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    form = CandidateAdminForm
    list_display = ['user', 'masked_name','first_name', 'last_name', 'role', 'experience_years', 'city', 'age', 'is_verified', 'is_active', 'is_available_for_hiring']
    list_filter = ['is_verified', 'role__category', 'religion', 'state', 'is_active', 'is_available_for_hiring', 'experience_years','joining_availability']
    search_fields = ['first_name', 'last_name', 'masked_name', 'user__email', 'skills','notice_period_details']
    readonly_fields = ['masked_name', 'created_at', 'updated_at', 'last_availability_update','declaration_agreed_at']
    raw_id_fields = ['user']
    inlines = [WorkExperienceInline, CareerGapInline, EducationInline, CertificationInline]
    actions = ['verify_candidates', 'unverify_candidates']

    fieldsets = (
        ('User Account', {
            'fields': ('user',)
        }),
        ('Basic Information', {
            'fields': ('first_name', 'last_name', 'masked_name', 'phone', 'age')
        }),
        ('Professional', {
            'fields': ('role', 'experience_years', 'skills')
        }),
        ('Availability', {
            'fields': ('joining_availability', 'notice_period_details')
        }),
        ('Personal', {
            'fields': ('religion', 'languages', 'street_address', 'willing_to_relocate', 'career_objective')
        }),
        ('Location', {
            'fields': ('country', 'state', 'city')
        }),
        ('Resume & Media', {
            'fields': ('resume', 'video_intro', 'profile_image')
        }),
        ('Status', {
            'fields': ('is_verified', 'is_active', 'is_available_for_hiring', 'last_availability_update','has_agreed_to_declaration', 'declaration_agreed_at', 'created_at', 'updated_at')
        })
    )

    def verify_candidates(self, request, queryset):
        count = queryset.update(is_verified=True)
        self.message_user(request, f'{count} candidate(s) verified successfully.')
    verify_candidates.short_description = '✅ Verify selected candidates'

    def unverify_candidates(self, request, queryset):
        count = queryset.update(is_verified=False)
        self.message_user(request, f'{count} candidate(s) unverified.')
    unverify_candidates.short_description = '❌ Unverify selected candidates'

@admin.register(UnlockHistory)
class UnlockHistoryAdmin(admin.ModelAdmin):
    list_display = ['hr_user', 'candidate', 'credits_used', 'unlocked_at']
    list_filter = ['unlocked_at', 'credits_used']
    search_fields = ['hr_user__user__email', 'candidate__masked_name']
    readonly_fields = ['unlocked_at']
    raw_id_fields = ['hr_user', 'candidate']  

@admin.register(CandidateNote)
class CandidateNoteAdmin(admin.ModelAdmin):
    list_display = ['hr_user', 'candidate', 'note_text_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['hr_user__user__email', 'candidate__masked_name', 'note_text']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['hr_user', 'candidate']
    
    def note_text_preview(self, obj):
        return obj.note_text[:50] + '...' if len(obj.note_text) > 50 else obj.note_text
    note_text_preview.short_description = 'Note Preview'

class CandidateFollowupInline(admin.TabularInline):
    model = CandidateFollowup
    extra = 0
    fields = ['hr_user', 'followup_date', 'notes', 'is_completed']
    readonly_fields = ['created_at']


@admin.register(CandidateFollowup)
class CandidateFollowupAdmin(admin.ModelAdmin):
    list_display = ['hr_user', 'candidate', 'followup_date', 'is_completed', 'is_upcoming', 'created_at']
    list_filter = ['is_completed', 'followup_date', 'created_at']
    search_fields = ['hr_user__user__email', 'candidate__masked_name', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['hr_user', 'candidate']
    actions = ['mark_as_completed', 'send_followup_reminder']

    def is_upcoming(self, obj):
        from django.utils import timezone
        if not obj.is_completed and obj.followup_date > timezone.now():
            return "Yes"
        return "No"
    is_upcoming.short_description = 'Upcoming'

    def mark_as_completed(self, request, queryset):
        count = queryset.update(is_completed=True)
        self.message_user(request, f'{count} follow-up(s) marked as completed.')
    mark_as_completed.short_description = 'Mark as completed'

    def send_followup_reminder(self, request, queryset):
        from apps.notifications.models import UserNotification, NotificationTemplate, NotificationLog
        from django.utils import timezone

        count = 0
        for followup in queryset.filter(is_completed=False):
            followup_time = followup.followup_date.strftime("%-d %B %Y at %-I:%M %p")
            candidate_name = followup.candidate.masked_name

            notification_title = "Follow-up Reminder"
            notification_body = f"Follow-up reminder for {candidate_name} scheduled at {followup_time}"

            try:
                template = NotificationTemplate.objects.filter(
                    notification_type='FOLLOWUP_REMINDER',
                    is_active=True
                ).first()

                if template:
                    notification_title = template.title.format(
                        candidate_name=candidate_name,
                        followup_time=followup_time
                    )
                    notification_body = template.body.format(
                        candidate_name=candidate_name,
                        followup_time=followup_time,
                        notes=followup.notes or "No notes"
                    )
            except Exception:
                pass

            UserNotification.objects.create(
                user=followup.hr_user.user,
                title=notification_title,
                body=notification_body,
                data_payload={
                    'type': 'FOLLOWUP_REMINDER',
                    'followup_id': str(followup.id),
                    'candidate_id': str(followup.candidate.id)
                }
            )
            count += 1

        self.message_user(request, f'Sent {count} follow-up reminder(s).')
    send_followup_reminder.short_description = 'Send follow-up reminder now'

@admin.register(WorkExperience)
class WorkExperienceAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'company_name', 'role_title','current_ctc','start_date', 'end_date', 'is_current']
    list_filter = ['is_current', 'start_date']
    search_fields = ['candidate__masked_name', 'company_name', 'role_title']
    raw_id_fields = ['candidate']

    fieldsets = (
        ('Basic Info', {
            'fields': ('candidate',)
        }),
        ('Work Details', {
            'fields': ('company_name', 'role_title', 'location', 'current_ctc', 'description'),
        }),
        ('Timeline', {
            'fields': ('start_date', 'end_date', 'is_current')
        }),
    )

@admin.register(CareerGap)
class CareerGapAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'start_date', 'end_date', 'gap_duration', 'gap_reason_preview']
    list_filter = ['start_date', 'end_date']
    search_fields = ['candidate__masked_name', 'gap_reason']
    raw_id_fields = ['candidate']

    def gap_duration(self, obj):
        if obj.start_date and obj.end_date:
            months = ((obj.end_date.year - obj.start_date.year) * 12) + (obj.end_date.month - obj.start_date.month)
            return f"{months} months"
        return "-"
    gap_duration.short_description = 'Duration'

    def gap_reason_preview(self, obj):
        return obj.gap_reason[:50] + '...' if len(obj.gap_reason) > 50 else obj.gap_reason
    gap_reason_preview.short_description = 'Reason'

# @admin.register(Education)  # Removed from sidebar - accessible via Candidate inline
class EducationAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'institution_name', 'degree', 'start_year', 'end_year', 'is_ongoing']
    list_filter = ['is_ongoing', 'start_year']
    search_fields = ['candidate__masked_name', 'institution_name', 'degree']
    raw_id_fields = ['candidate']


@admin.register(HiringAvailabilityUI)
class HiringAvailabilityUIAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'button_layout', 'background_type', 'updated_at']
    list_filter = ['is_active', 'button_layout', 'background_type']
    search_fields = ['name', 'title', 'message']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Configuration Info', {
            'fields': ('name', 'is_active')
        }),
        ('Content', {
            'fields': ('title', 'message'),
            'description': 'Main title and message text shown to candidates'
        }),
        ('Layout', {
            'fields': ('button_layout', 'content_vertical_alignment'),
            'description': 'Choose how buttons are arranged (column/row) and vertical position of content (top/center/bottom)'
        }),
        ('Background Settings', {
            'fields': ('background_type', 'background_color', 'background_image', 'gradient_start_color', 'gradient_end_color'),
            'description': 'Background can be solid color, image, or gradient'
        }),
        ('Icon Configuration', {
            'fields': ('show_icon', 'icon_source', 'icon_type', 'icon_image', 'icon_size', 'icon_color', 'icon_background_color'),
            'description': 'Icon displayed at the top of the screen. Choose Material Icon (built-in) or Upload custom icon/image'
        }),
        ('Title Styling', {
            'fields': ('title_font_size', 'title_font_weight', 'title_color', 'title_alignment'),
            'description': 'Customize title appearance'
        }),
        ('Message Styling', {
            'fields': ('message_font_size', 'message_font_weight', 'message_color', 'message_alignment'),
            'description': 'Customize message appearance'
        }),
        ('Primary Button (Yes/Available)', {
            'fields': (
                'primary_button_text',
                'primary_button_bg_color',
                'primary_button_text_color',
                'primary_button_font_size',
                'primary_button_font_weight',
                'primary_button_height',
                'primary_button_border_radius'
            ),
            'description': 'Customize the "Yes, I\'m Available" button'
        }),
        ('Secondary Button (No/Not Available)', {
            'fields': (
                'secondary_button_text',
                'secondary_button_bg_color',
                'secondary_button_text_color',
                'secondary_button_border_color',
                'secondary_button_font_size',
                'secondary_button_font_weight',
                'secondary_button_height',
                'secondary_button_border_radius'
            ),
            'description': 'Customize the "No, Not Available" button'
        }),
        ('Spacing & Padding', {
            'fields': ('spacing_between_buttons', 'content_padding_horizontal', 'content_padding_vertical'),
            'description': 'Control spacing between elements'
        }),
        ('Extra Content (Advanced)', {
            'fields': ('extra_content',),
            'description': 'Add dynamic extra content sections in JSON format. Example: [{"type": "text", "content": "Extra information", "position": "top", "font_size": 14, "color": "#666666"}]'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        # Ensure only one configuration is active
        if obj.is_active:
            HiringAvailabilityUI.objects.filter(is_active=True).exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


# @admin.register(FilterOption)  # Accessible via FilterCategory inline only
class FilterOptionAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'category', 'approval_badge', 'is_active',
        'submitted_by', 'submitted_at', 'created_at'
    ]
    list_filter = ['is_approved', 'is_active', 'category', 'submitted_at']
    search_fields = ['name', 'submitted_by__email']
    readonly_fields = ['submitted_by', 'submitted_at', 'approved_by', 'approved_at']
    actions = ['approve_options', 'reject_options']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('category', 'name', 'slug', 'parent', 'icon', 'display_order')
        }),
        ('Status', {
            'fields': ('is_active', 'is_approved')
        }),
        ('Submission Details', {
            'fields': ('submitted_by', 'submitted_at', 'approved_by', 'approved_at'),
            'classes': ('collapse',)
        }),
    )
    
    def approval_badge(self, obj):
        if obj.is_approved:
            return "✅ Approved"
        return "⏳ Pending Approval"
    approval_badge.short_description = 'Status'
    
    def approve_options(self, request, queryset):
        from django.utils import timezone
        count = 0
        for option in queryset.filter(is_approved=False):
            option.is_approved = True
            option.approved_by = request.user
            option.approved_at = timezone.now()
            option.is_active = True
            option.save()
            count += 1
        
        self.message_user(request, f'{count} option(s) approved successfully.')
    approve_options.short_description = '✅ Approve selected options'
    
    def reject_options(self, request, queryset):
        count = queryset.filter(is_approved=False).update(is_active=False, is_approved=False)
        self.message_user(request, f'{count} option(s) rejected.')
    reject_options.short_description = '❌ Reject selected options'


@admin.register(ProfileTip)
class ProfileTipAdmin(admin.ModelAdmin):
    list_display = ['title', 'subtitle', 'display_order', 'is_active', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'subtitle']
    ordering = ['display_order', 'title']
    
    fieldsets = (
        ('Tip Information', {
            'fields': ('title', 'subtitle', 'icon_type')
        }),
        ('Instructions', {
            'fields': ('instructions',),
            'description': 'Enter instructions as JSON array. Example: ["Go to Edit Profile", "Tap on profile picture", "Choose from gallery"]'
        }),
        ('Display Settings', {
            'fields': ('display_order', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['created_at', 'updated_at']