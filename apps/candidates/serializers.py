from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Candidate, ProfileTip, UnlockHistory, FilterCategory, FilterOption, CandidateNote, CandidateFollowup, WorkExperience, Education, CareerGap, Certification
from django.utils import timezone
import pytz

User = get_user_model()

class WorkExperienceSerializer(serializers.ModelSerializer):
    company_logo = serializers.SerializerMethodField()

    class Meta:
        model = WorkExperience
        fields = ['id', 'company_name', 'company_logo', 'role_title', 'start_date', 'end_date', 'is_current', 'current_ctc','location', 'description']

    def get_company_logo(self, obj):
        """Get company logo from Company model if exists"""
        from apps.recruiters.models import Company

        try:
            company = Company.objects.get(name__iexact=obj.company_name)
            if company.logo:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(company.logo.url)
                return company.logo.url
        except Company.DoesNotExist:
            pass
        return None

class CareerGapSerializer(serializers.ModelSerializer):
    class Meta:
        model = CareerGap
        fields = ['id', 'start_date', 'end_date', 'gap_reason']

class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = ['id', 'institution_name', 'degree', 'field_of_study', 'start_year', 'end_year', 'is_ongoing', 'grade_percentage', 'location']

class CertificationSerializer(serializers.ModelSerializer):
    document_url = serializers.SerializerMethodField()
    organization_logo = serializers.SerializerMethodField()

    class Meta:
        model = Certification
        fields = ['id', 'certification_name', 'issuing_organization', 'issue_date', 'document_url', 'organization_logo']

    def get_document_url(self, obj):
        if obj.document:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.document.url)
            return obj.document.url
        return None

    def get_organization_logo(self, obj):
        from apps.recruiters.models import Company
        try:
            company = Company.objects.get(name__iexact=obj.issuing_organization)
            if company.logo:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(company.logo.url)
                return company.logo.url
        except Company.DoesNotExist:
            pass
        return None

class CandidateNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateNote
        fields = ['id', 'note_text', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class CandidateFollowupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateFollowup
        fields = ['id', 'followup_date', 'notes', 'is_completed', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class CandidateRegistrationSerializer(serializers.ModelSerializer):
    role = serializers.CharField(write_only=True)
    religion = serializers.CharField(write_only=True)
    country = serializers.CharField(write_only=True)
    state = serializers.CharField(write_only=True)
    city = serializers.CharField(write_only=True)
    
    class Meta:
        model = Candidate
        fields = [
           'first_name','last_name', 'phone', 'age', 'role', 'experience_years',
             'religion', 'country',
            'state', 'city', 'skills', 'resume', 'video_intro', 'profile_image',
            'languages', 'street_address', 'willing_to_relocate', 'career_objective','joining_availability', 'notice_period_details'
        ]
        extra_kwargs = {
        'first_name': {'required': True},
        'last_name': {'required': True},
        'phone': {'required': True},
        'age': {'required': True},
        'role': {'required': True},
        'state': {'required': True},
        'city': {'required': True},
        'religion': {'required': True},
        'languages': {'required': True},
        'street_address': {'required': True},
        'career_objective': {'required': True},
        'joining_availability': {'required': True},
        'notice_period_details': {'required': True},  
        'resume': {'required': True},
        'video_intro': {'required': True},
        'profile_image': {'required': True},
        'experience_years': {'required': True},
        'country': {'required': True},
        'skills': {'required': True},
        'willing_to_relocate': {'required': True}
    }
    
    def validate_willing_to_relocate(self, value):
        """Convert YES/NO to boolean"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.upper() == 'YES'
        return False
    
    def validate(self, data):
        from django.utils import timezone
        
        # Validate notice period
        if data.get('joining_availability') == 'NOTICE_PERIOD':
            if not data.get('notice_period_details'):
                raise serializers.ValidationError({
                    'notice_period_details': 'Required when joining availability is notice period'
                })
        
        # Get or create categories
        dept_category, _ = FilterCategory.objects.get_or_create(
            slug='department',
            defaults={'name': 'Department', 'display_order': 1}
        )
        religion_category, _ = FilterCategory.objects.get_or_create(
            slug='religion', 
            defaults={'name': 'Religion', 'display_order': 2}
        )
        country_category, _ = FilterCategory.objects.get_or_create(
            slug='country',
            defaults={'name': 'Country', 'display_order': 3}
        )
        state_category, _ = FilterCategory.objects.get_or_create(
            slug='state',
            defaults={'name': 'State', 'display_order': 4}
        )
        city_category, _ = FilterCategory.objects.get_or_create(
            slug='city',
            defaults={'name': 'City', 'display_order': 5}
        )

        # ========== HANDLE ROLE ==========
        role_value = data.get('role')
        if role_value and not isinstance(role_value, FilterOption):
            role_slug = role_value.lower().replace(' ', '-')
            
            # Check if ANY FilterOption with this slug exists (approved or not)
            role = FilterOption.objects.filter(
                category=dept_category,
                slug=role_slug
            ).first()
            
            if role:
                # Use existing FilterOption
                data['role'] = role
            else:
                # Role doesn't exist, check if "Other" option exists
                other_option = FilterOption.objects.filter(
                    category=dept_category,
                    name__iexact='other',
                    is_approved=True
                ).first()
                
                if other_option and role_value.lower() != 'other':
                    # Custom role - create as UNAPPROVED
                    data['role'] = FilterOption.objects.create(
                        category=dept_category,
                        slug=role_slug,
                        name=role_value,
                        is_active=False,
                        is_approved=False,
                        submitted_by=self.context['request'].user,
                        submitted_at=timezone.now()
                    )
                else:
                    # Pre-defined option - create as APPROVED
                    data['role'] = FilterOption.objects.create(
                        category=dept_category,
                        slug=role_slug,
                        name=role_value,
                        is_active=True,
                        is_approved=True
                    )

        # ========== HANDLE RELIGION ==========
        religion_value = data.get('religion')
        if religion_value and not isinstance(religion_value, FilterOption):
            religion_slug = religion_value.lower().replace(' ', '-')
            
            # Check if ANY FilterOption with this slug exists (approved or not)
            religion = FilterOption.objects.filter(
                category=religion_category,
                slug=religion_slug
            ).first()
            
            if religion:
                # Use existing FilterOption
                data['religion'] = religion
            else:
                # Religion doesn't exist, check if "Other" option exists
                other_option = FilterOption.objects.filter(
                    category=religion_category,
                    name__iexact='other',
                    is_approved=True
                ).first()
                
                if other_option and religion_value.lower() != 'other':
                    # Custom religion - create as UNAPPROVED
                    data['religion'] = FilterOption.objects.create(
                        category=religion_category,
                        slug=religion_slug,
                        name=religion_value,
                        is_active=False,
                        is_approved=False,
                        submitted_by=self.context['request'].user,
                        submitted_at=timezone.now()
                    )
                else:
                    # Pre-defined option - create as APPROVED
                    data['religion'] = FilterOption.objects.create(
                        category=religion_category,
                        slug=religion_slug,
                        name=religion_value,
                        is_active=True,
                        is_approved=True
                    )

        # ========== HANDLE COUNTRY ==========
        country_value = data.get('country', 'India')
        if not isinstance(country_value, FilterOption):
            country_slug = country_value.lower().replace(' ', '-')
            
            # Check if country exists
            country = FilterOption.objects.filter(
                category=country_category,
                slug=country_slug
            ).first()
            
            if not country:
                country = FilterOption.objects.create(
                    category=country_category,
                    slug=country_slug,
                    name=country_value,
                    is_active=True,
                    is_approved=True
                )
            
            data['country'] = country
        else:
            data['country'] = country_value

        # ========== HANDLE STATE ==========
        state_value = data.get('state')
        state = None
        
        if state_value and not isinstance(state_value, FilterOption):
            state_slug = state_value.lower().replace(' ', '-')
            
            # Check if state exists
            state = FilterOption.objects.filter(
                category=state_category,
                slug=state_slug
            ).first()
            
            if not state:
                # State doesn't exist, check if "Other" option exists
                other_option = FilterOption.objects.filter(
                    category=state_category,
                    name__iexact='other',
                    is_approved=True
                ).first()
                
                if other_option and state_value.lower() != 'other':
                    # Custom state - create as UNAPPROVED
                    state = FilterOption.objects.create(
                        category=state_category,
                        slug=state_slug,
                        name=state_value.title(),
                        parent=data.get('country'),
                        is_active=False,
                        is_approved=False,
                        submitted_by=self.context['request'].user,
                        submitted_at=timezone.now()
                    )
                else:
                    # Pre-defined option - create as APPROVED
                    state = FilterOption.objects.create(
                        category=state_category,
                        slug=state_slug,
                        name=state_value.title(),
                        parent=data.get('country'),
                        is_active=True,
                        is_approved=True
                    )
        elif isinstance(state_value, FilterOption):
            state = state_value
        
        data['state'] = state

        # ========== HANDLE CITY ==========
        city_value = data.get('city')
        if city_value and state and not isinstance(city_value, FilterOption):
            city_slug = f"{state.slug}-{city_value.lower().replace(' ', '-')}"
            
            # Check if city exists
            city = FilterOption.objects.filter(
                category=city_category,
                slug=city_slug
            ).first()
            
            if not city:
                # City doesn't exist, check if "Other" option exists
                other_option = FilterOption.objects.filter(
                    category=city_category,
                    name__iexact='other',
                    is_approved=True
                ).first()
                
                if other_option and city_value.lower() != 'other':
                    # Custom city - create as UNAPPROVED
                    city = FilterOption.objects.create(
                        category=city_category,
                        slug=city_slug,
                        name=city_value.title(),
                        parent=state,
                        is_active=False,
                        is_approved=False,
                        submitted_by=self.context['request'].user,
                        submitted_at=timezone.now()
                    )
                else:
                    # Pre-defined option - create as APPROVED
                    city = FilterOption.objects.create(
                        category=city_category,
                        slug=city_slug,
                        name=city_value.title(),
                        parent=state,
                        is_active=True,
                        is_approved=True
                    )
            
            data['city'] = city
        elif isinstance(city_value, FilterOption):
            data['city'] = city_value

        return data


def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)

def update(self, instance, validated_data):
        validated_data = self.validate(validated_data)
        return super().update(instance, validated_data)


class MaskedCandidateSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    profile_image_url = serializers.SerializerMethodField()
    experience_years = serializers.SerializerMethodField()
    credits_required = serializers.SerializerMethodField()
    rank = serializers.SerializerMethodField()
    current_role_title = serializers.SerializerMethodField()


    class Meta:
        model = Candidate
        fields = [
            'id', 'masked_name', 'role_name', 'current_role_title', 'experience_years',
            'city_name', 'age', 'skills', 'profile_image_url', 'is_active', 'is_available_for_hiring', 'is_verified', 'credits_required', 'rank'
        ]
    
    def get_profile_image_url(self, obj):
        if hasattr(obj, 'profile_image') and obj.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
            return obj.profile_image.url
        return None
    def get_experience_years(self, obj):
        """Calculate total experience in years and months from work_experiences"""
        from datetime import datetime
        
        work_experiences = obj.work_experiences.all()
        if not work_experiences:
            exp_years = obj.experience_years or 0
            if exp_years == 0:
                return "0 Yr"
            else:
                return f"{exp_years} Yr"
        
        total_months = 0
        for exp in work_experiences:
            start_date = exp.start_date
            end_date = exp.end_date if exp.end_date else datetime.now().date()
            
            # Calculate total months
            months_diff = ((end_date.year - start_date.year) * 12) + (end_date.month - start_date.month)
            total_months += months_diff
        
        # Calculate years and remaining months
        years = total_months // 12
        months = total_months % 12
        
        # Format the output
        if years == 0 and months == 0:
            return "0 Yr"
        elif years == 0:
            return f"{months} Mo"
        elif months == 0:
            return f"{years} Yr"
        else:
            return f"{years} Yr {months} Mo"

    def get_credits_required(self, obj):
        """Get credits required to unlock this candidate"""
        try:
            return obj.rank.credits_required
        except:
            return 10  # Default BRONZE tier minimum

    def get_rank(self, obj):
        """Get ranking score for masked candidate to enable sorting"""
        from apps.ranking.services import get_candidate_rank_breakdown
        try:
            return get_candidate_rank_breakdown(obj)
        except Exception as e:
            return None

    def get_current_role_title(self, obj):
        """Get the latest/current role title from work experiences"""
        # Get the most recent work experience (is_current=True or latest end_date)
        current_exp = obj.work_experiences.filter(is_current=True).first()

        if current_exp:
            return current_exp.role_title

        # If no current experience, get the latest one by end_date
        latest_exp = obj.work_experiences.order_by('-end_date').first()

        if latest_exp:
            return latest_exp.role_title

        # Fallback to role_name if no work experience
        return obj.role.name if obj.role else None

class FullCandidateSerializer(serializers.ModelSerializer):
    skills_list = serializers.SerializerMethodField()
    email = serializers.CharField(source='user.email', read_only=True)
    credits_used = serializers.IntegerField(read_only=True, required=False)
    resume_url = serializers.SerializerMethodField()
    video_intro_url = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()
    last_availability_update = serializers.SerializerMethodField()

    role_name = serializers.CharField(source='role.name', read_only=True)
    religion_name = serializers.CharField(source='religion.name', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)

    work_experiences = WorkExperienceSerializer(many=True, read_only=True)
    career_gaps = CareerGapSerializer(many=True, read_only=True)
    educations = EducationSerializer(many=True, read_only=True)
    certifications = CertificationSerializer(many=True, read_only=True)
    experience_years = serializers.SerializerMethodField()
    rank = serializers.SerializerMethodField()


    class Meta:
        model = Candidate
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone', 'age',
            'role_name', 'experience_years',
            'religion_name', 'country_name', 'state_name', 'city_name',
            'skills', 'skills_list',
            'resume_url', 'video_intro_url', 'profile_image_url', 'credits_used',
            'languages', 'street_address', 'willing_to_relocate', 'career_objective',
            'work_experiences', 'career_gaps', 'educations', 'certifications', 'profile_step', 'is_profile_completed',
            'joining_availability', 'notice_period_details',
            'is_verified', 'is_available_for_hiring', 'last_availability_update',
            'has_agreed_to_declaration', 'declaration_agreed_at', 'rank'
        ]
    
    def get_skills_list(self, obj):
        return obj.get_skills_list()
    
    def get_resume_url(self, obj):
        if obj.resume:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.resume.url)
            return obj.resume.url
        return None
        
    def get_video_intro_url(self, obj):
        if obj.video_intro:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.video_intro.url)
            return obj.video_intro.url
        return None

    def get_profile_image_url(self, obj):
        if hasattr(obj, 'profile_image') and obj.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
            return obj.profile_image.url
        return None
    
    def get_experience_years(self, obj):
        """Calculate total experience in years from work_experiences"""
        from datetime import datetime
        
        work_experiences = obj.work_experiences.all()
        if not work_experiences:
           exp_years = obj.experience_years or 0
           if exp_years == 0:
               return "0 Yr"
           else:
                return f"{exp_years} Yr"
        
        total_months = 0
        for exp in work_experiences:
            start_date = exp.start_date
            end_date = exp.end_date if exp.end_date else datetime.now().date()
            months_diff = ((end_date.year - start_date.year) * 12) + (end_date.month - start_date.month)
            total_months += months_diff
    
        years = total_months // 12
        months = total_months % 12
    
        if years == 0 and months == 0:
           return "0 Yr"
        elif years == 0:
           return f"{months} Mo"
        elif months == 0:
          return f"{years} Yr"
        else:
           return f"{years} Yr {months} Mo"

    def get_last_availability_update(self, obj):
        if obj.last_availability_update:
            ist = pytz.timezone('Asia/Kolkata')
            ist_time = obj.last_availability_update.astimezone(ist)
            return ist_time.strftime('%d %b %Y, %I:%M %p IST')
        return None

    def get_rank(self, obj):
        from apps.ranking.services import get_candidate_rank_breakdown
        try:
            return get_candidate_rank_breakdown(obj)
        except Exception as e:
            return None
    



class UnlockHistorySerializer(serializers.ModelSerializer):
    candidate_name = serializers.CharField(source='candidate.masked_name', read_only=True)
    hr_email = serializers.CharField(source='hr_user.user.email', read_only=True)
    
    class Meta:
        model = UnlockHistory
        fields = [
            'id', 'candidate_name', 'hr_email', 'credits_used', 'unlocked_at'
        ]
        read_only_fields = ['unlocked_at']


class FilterCategorySerializer(serializers.ModelSerializer):
    options_count = serializers.SerializerMethodField()
    icon_url = serializers.SerializerMethodField()
    
    class Meta:
        model = FilterCategory
        fields = [
            'id', 'name', 'slug', 'icon_url', 'display_order', 
            'is_active', 'options_count', 'created_at', 
            'bento_grid', 'dashboard_display', 'inner_filter'
        ]
    
    def get_options_count(self, obj):
        return obj.options.filter(is_active=True).count()
    
    def get_icon_url(self, obj):
        if obj.icon:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.icon.url)
            return obj.icon.url
        return None


class FilterOptionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    candidates_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FilterOption
        fields = [
            'id', 'name', 'slug', 'category_name', 'parent_name',
            'display_order', 'is_active', 'candidates_count', 'created_at'
        ]
    
    def get_candidates_count(self, obj):
        from django.db.models import Q
        count = Candidate.objects.filter(
            Q(role=obj) | Q(religion=obj) | Q(country=obj) | 
            Q(state=obj) | Q(city=obj),
            is_active=True
        ).count()
        return count


class CandidateUpdateSerializer(serializers.ModelSerializer):
    role = serializers.CharField(required=False)
    religion = serializers.CharField(required=False)
    country = serializers.CharField(required=False)
    state = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    
    class Meta:
        model = Candidate
        fields = [
            'first_name', 'last_name', 'phone', 'age', 'role', 'experience_years',
            'current_ctc', 'expected_ctc', 'religion', 'country',
            'state', 'city', 'skills', 'resume', 'video_intro','profile_image',
            'languages', 'street_address', 'willing_to_relocate', 'work_experience', 'career_objective','joining_availability', 'notice_period_details'
        ]
        extra_kwargs = {
            'resume': {'required': False, 'allow_null': True},
            'video_intro': {'required': False, 'allow_null': True},
            'profile_image': {'required': True, 'allow_null': False},
            'languages': {'required': False, 'allow_blank': True},
            'street_address': {'required': False, 'allow_blank': True},
            'willing_to_relocate': {'required': False},
            'work_experience': {'required': False, 'allow_blank': True},
            'career_objective': {'required': False, 'allow_blank': True},
            'joining_availability': {'required': False},
            'notice_period_details': {'required': True},
        }

    def validate(self, data):
        return self._convert_to_filter_options(data)
        
    def _convert_to_filter_options(self, data):
        dept_category, _ = FilterCategory.objects.get_or_create(
            slug='department',
            defaults={'name': 'Department', 'display_order': 1}
        )
        religion_category, _ = FilterCategory.objects.get_or_create(
            slug='religion',
            defaults={'name': 'Religion', 'display_order': 2}
        )
        country_category, _ = FilterCategory.objects.get_or_create(
            slug='country',
            defaults={'name': 'Country', 'display_order': 3}
        )
        state_category, _ = FilterCategory.objects.get_or_create(
            slug='state',
            defaults={'name': 'State', 'display_order': 4}
        )
        city_category, _ = FilterCategory.objects.get_or_create(
            slug='city',
            defaults={'name': 'City', 'display_order': 5}
        )
        
        role_value = data.get('role')
        if role_value and not isinstance(role_value, FilterOption):
            role_slug = role_value.lower().replace(' ', '-')
            try:
                data['role'] = FilterOption.objects.get(category=dept_category, slug=role_slug)
            except FilterOption.DoesNotExist:
                # Check if "Other" option exists in this category
                other_option = FilterOption.objects.filter(
                    category=dept_category,
                    name__iexact='other'
                ).first()
                
                # If user selected "Other" and provided custom text, create as INACTIVE
                if other_option and role_value.lower() != 'other':
                    data['role'] = FilterOption.objects.create(
                        category=dept_category,
                        slug=role_slug,
                        name=role_value,
                        is_active=False
                    )
                else:
                    # For pre-defined options or when "Other" itself is selected
                    data['role'] = FilterOption.objects.create(
                        category=dept_category,
                        slug=role_slug,
                        name=role_value,
                        is_active=True
                    )

        
        religion_value = data.get('religion')
        if religion_value and not isinstance(religion_value, FilterOption):
            religion_slug = religion_value.lower().replace(' ', '-')
            try:
                data['religion'] = FilterOption.objects.get(category=religion_category, slug=religion_slug)
            except FilterOption.DoesNotExist:
                # Check if "Other" option exists
                other_option = FilterOption.objects.filter(
                    category=religion_category,
                    name__iexact='other'
                ).first()
                
                if other_option and religion_value.lower() != 'other':
                    data['religion'] = FilterOption.objects.create(
                        category=religion_category,
                        slug=religion_slug,
                        name=religion_value,
                        is_active=False
                    )
                else:
                    data['religion'] = FilterOption.objects.create(
                        category=religion_category,
                        slug=religion_slug,
                        name=religion_value,
                        is_active=True
                    )
        
        country_value = data.get('country', 'India')
        if not isinstance(country_value, FilterOption):
            country_slug = country_value.lower().replace(' ', '-')
            try:
                country = FilterOption.objects.get(category=country_category, slug=country_slug)
            except FilterOption.DoesNotExist:
                country = FilterOption.objects.create(
                    category=country_category,
                    slug=country_slug,
                    name=country_value,
                    is_active=True
                )
            data['country'] = country
        
        state_value = data.get('state')
        state = None
        if state_value and not isinstance(state_value, FilterOption):
            state_slug = state_value.lower().replace(' ', '-')
            try:
                state = FilterOption.objects.get(category=state_category, slug=state_slug)
            except FilterOption.DoesNotExist:
                # Check if "Other" option exists
                other_option = FilterOption.objects.filter(
                    category=state_category,
                    name__iexact='other'
                ).first()
                
                if other_option and state_value.lower() != 'other':
                    state = FilterOption.objects.create(
                        category=state_category,
                        slug=state_slug,
                        name=state_value.title(),
                        parent=data.get('country'),
                        is_active=False
                    )
                else:
                    state = FilterOption.objects.create(
                        category=state_category,
                        slug=state_slug,
                        name=state_value.title(),
                        parent=data.get('country'),
                        is_active=True
                    )
            data['state'] = state
        elif isinstance(state_value, FilterOption):
            state = state_value
            data['state'] = state

        
        city_value = data.get('city')
        if city_value and state and not isinstance(city_value, FilterOption):
            city_slug = f"{state.slug}-{city_value.lower().replace(' ', '-')}"
            try:
                data['city'] = FilterOption.objects.get(category=city_category, slug=city_slug)
            except FilterOption.DoesNotExist:
                # Check if "Other" option exists
                other_option = FilterOption.objects.filter(
                    category=city_category,
                    name__iexact='other'
                ).first()
                
                if other_option and city_value.lower() != 'other':
                    data['city'] = FilterOption.objects.create(
                        category=city_category,
                        slug=city_slug,
                        name=city_value.title(),
                        parent=state,
                        is_active=False
                    )
                else:
                    data['city'] = FilterOption.objects.create(
                        category=city_category,
                        slug=city_slug,
                        name=city_value.title(),
                        parent=state,
                        is_active=True
                    )
        
        return data

    def update(self, instance, validated_data):
        validated_data.pop('user', None)
        return super().update(instance, validated_data)
    
class ProfileTipSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileTip
        fields = ['id', 'title', 'subtitle', 'icon_type', 'instructions', 'display_order']    