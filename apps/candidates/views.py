from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes,parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from datetime import datetime
from django.utils import timezone

from apps.recruiters.models import HRProfile
from django.contrib.auth import get_user_model
from .models import *
from .serializers import (
    CandidateRegistrationSerializer,
    MaskedCandidateSerializer, 
    FullCandidateSerializer,
    CandidateNoteSerializer,
    CandidateFollowupSerializer,
    FilterCategorySerializer
)
from apps.notifications.services import WorkfinaFCMService
from apps.notifications.models import ProfileStepReminder
from apps.wallet.models import Wallet


User = get_user_model()

class CandidateRegistrationView(generics.CreateAPIView):
    """API for candidates to register their profile"""
    
    serializer_class = CandidateRegistrationSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, *args, **kwargs):
      
        # Check if user is candidate
        if request.user.role != 'candidate':
            return Response({
                'error': 'Only candidates can create candidate profiles'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check if profile already exists
        if hasattr(request.user, 'candidate_profile'):
            return Response({
                'error': 'Candidate profile already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        work_experience_data = request.data.get('work_experience')
        education_data = request.data.get('education')
        certifications_data = request.data.get('certifications')

        # Call parent create method first
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 201:
            try:
                candidate = Candidate.objects.get(user=request.user)
                
                if work_experience_data:
                    try:
                        import json
                        work_exp_list = json.loads(work_experience_data)

                        for exp_data in work_exp_list:

                            is_gap = exp_data.get('is_gap_period', False)

                            if is_gap:
                                # Save as CareerGap
                                CareerGap.objects.create(
                                    candidate=candidate,
                                    start_date=f"{exp_data.get('start_year')}-{_month_to_number(exp_data.get('start_month'))}-01",
                                    end_date=f"{exp_data.get('end_year')}-{_month_to_number(exp_data.get('end_month'))}-01",
                                    gap_reason=exp_data.get('gap_reason', '')
                                )
                                print(f"✅ Saved career gap: {exp_data.get('gap_reason')}")
                            else:
                                # Save as WorkExperience
                                WorkExperience.objects.create(
                                    candidate=candidate,
                                    company_name=exp_data.get('company_name', ''),
                                    role_title=exp_data.get('role_title', ''),
                                    start_date=f"{exp_data.get('start_year')}-{_month_to_number(exp_data.get('start_month'))}-01",
                                    end_date=f"{exp_data.get('end_year')}-{_month_to_number(exp_data.get('end_month'))}-01" if not exp_data.get('is_current') and exp_data.get('end_year') else None,
                                    is_current=exp_data.get('is_current', False),
                                    current_ctc=float(exp_data.get('ctc')) if exp_data.get('ctc') and exp_data.get('ctc').strip() else None,
                                    location=exp_data.get('location', ''),
                                    description=exp_data.get('description', ''),
                                )
                                print(f"✅ Saved work experience: {exp_data.get('company_name')}")
                    except Exception as e:
                        print(f"❌ Work experience error: {e}")
                        import traceback
                        traceback.print_exc()
                
                # ✅ SAVE EDUCATION
                if education_data:
                    try:
                        import json
                        edu_list = json.loads(education_data)
                        
                        print("=" * 50)
                        print("SAVING EDUCATION:")
                        print(json.dumps(edu_list, indent=2))
                        print("=" * 50)
                        
                        for edu_data in edu_list:
                            Education.objects.create(
                                candidate=candidate,
                                institution_name=edu_data.get('school', ''),
                                degree=edu_data.get('degree', ''),
                                field_of_study=edu_data.get('field', ''),
                                start_year=int(edu_data.get('start_year', 2020)),
                                end_year=int(edu_data.get('end_year', 2024)),
                                is_ongoing=False,
                                grade_percentage=float(edu_data.get('grade', '0').replace('%', '')) if edu_data.get('grade') else None,
                                location=''
                            )
                            print(f"✅ Saved education: {edu_data.get('school')}")
                    except Exception as e:
                        print(f"❌ Education error: {e}")
                        import traceback
                        traceback.print_exc()
                
                # ✅ SAVE CERTIFICATIONS
                if certifications_data:
                    try:
                        import json
                        cert_list = json.loads(certifications_data)

                        for i, cert_data in enumerate(cert_list):
                            Certification.objects.create(
                                candidate=candidate,
                                certification_name=cert_data.get('certification_name', ''),
                                issuing_organization=cert_data.get('issuing_organization', ''),
                                issue_date=cert_data.get('issue_date', ''),
                                document=request.FILES.get(f'certification_doc_{i}'),
                            )
                    except Exception as e:
                        print(f"❌ Certifications error: {e}")
                        import traceback
                        traceback.print_exc()

                # Return full profile data with work_experiences, career_gaps, educations and certifications
                candidate.refresh_from_db()

                candidate = Candidate.objects.prefetch_related('educations', 'work_experiences', 'career_gaps', 'certifications').get(id=candidate.id)

                serializer = FullCandidateSerializer(candidate, context={'request': request})
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                print(f"❌ Error saving work/education: {e}")
                import traceback
                traceback.print_exc()
        
        return response

class CandidateListView(generics.ListAPIView):
    """API to list masked candidates with filters - For HR users"""

    queryset = Candidate.objects.filter(is_active=True, is_available_for_hiring=True)
    serializer_class = MaskedCandidateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['role', 'city', 'state', 'religion', 'is_available_for_hiring']
    search_fields = ['skills']
    
    def get(self, request, *args, **kwargs):
        # Only HR users can view candidate list
        if request.user.role != 'hr':
            return Response({
                'error': 'Only HR users can view candidates'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Experience range filter
        min_exp = self.request.query_params.get('min_experience')
        max_exp = self.request.query_params.get('max_experience')
        
        if min_exp:
            queryset = queryset.filter(experience_years__gte=min_exp)
        if max_exp:
            queryset = queryset.filter(experience_years__lte=max_exp)
            
        return queryset

    def get_serializer(self, *args, **kwargs):
        # Get unlocked candidate IDs for current HR user
        unlocked_ids = UnlockHistory.objects.filter(
            hr_user=self.request.user.hr_profile
        ).values_list('candidate_id', flat=True)
        
        # Use different serializers based on unlock status
        if hasattr(self, 'object_list'):
            serialized_data = []
            for candidate in self.object_list:
                if candidate.id in unlocked_ids:
                    serializer = FullCandidateSerializer(candidate)
                else:
                    serializer = MaskedCandidateSerializer(candidate)
                serialized_data.append(serializer.data)
            return serialized_data
        
        return super().get_serializer(*args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        self.object_list = queryset
        serializer_data = self.get_serializer()
        return Response(serializer_data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unlock_candidate(request, candidate_id):
    """API to unlock candidate profile using credits - For HR users"""
    
    # Only HR users can unlock
    if request.user.role != 'hr':
        return Response({
            'error': 'Only HR users can unlock candidates'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        candidate = Candidate.objects.get(id=candidate_id, is_active=True)
        
        # Check if already unlocked
        if UnlockHistory.objects.filter(hr_user=request.user.hr_profile, candidate=candidate).exists():
            # Return full data if already unlocked
            serializer = FullCandidateSerializer(candidate)
            return Response({
                'success': True,
                'message': 'Already unlocked',
                'candidate': serializer.data,
                'already_unlocked': True
            })
        

        try:
            wallet = Wallet.objects.get(hr_profile__user=request.user)

            # Dynamic credits from ranking system
            try:
                credits_required = candidate.rank.credits_required
            except:
                credits_required = 5  # Default BRONZE tier

            # Check if user can unlock (checks subscription + wallet)
            if not wallet.can_unlock(credits_required):
                return Response({
                    'error': f'Insufficient credits. You need {credits_required} credits but have {wallet.balance}.',
                    'required_credits': credits_required,
                    'current_balance': wallet.balance
                }, status=status.HTTP_400_BAD_REQUEST)

            # Deduct credits (handles subscription + wallet automatically)
            old_balance = wallet.balance
            if not wallet.deduct_credits(credits_required):
                return Response({
                    'error': 'Failed to deduct credits. Please try again.',
                    'required_credits': credits_required,
                    'current_balance': wallet.balance
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create unlock history
            UnlockHistory.objects.create(
                hr_user=request.user.hr_profile,
                candidate=candidate,
                credits_used=credits_required
            )
            
            # Create wallet transaction
            from apps.wallet.models import WalletTransaction
            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type='UNLOCK',
                credits_used=credits_required,
                description=f'Unlocked candidate: {candidate.masked_name}'
            )
            # Send credit deduction notification
            try:
                WorkfinaFCMService.send_to_user(
                    user=request.user,
                    title=f"Profile Unlocked! 🔓",
                    body=f"You unlocked {candidate.masked_name}'s profile for {credits_required} credits. Balance: {wallet.balance}",
                    notification_type='CREDIT_UPDATE',
                    data={
                        'candidate_id': str(candidate.id),
                        'candidate_name': candidate.masked_name,
                        'credits_used': credits_required,
                        'old_balance': old_balance,
                        'new_balance': wallet.balance,
                        'action': 'unlock_profile'
                    }
                )
                print(f'[DEBUG] Sent unlock notification to {request.user.email}')
            except Exception as e:
                print(f'[DEBUG] Failed to send unlock notification: {str(e)}')
            
                       
            
            # Return full candidate data
            serializer = FullCandidateSerializer(candidate)
            return Response({
                'success': True,
                'message': 'Profile unlocked successfully',
                'candidate': serializer.data,
                'credits_used': credits_required,
                'remaining_balance': wallet.balance,
                'already_unlocked': False
            })
            
        except Wallet.DoesNotExist:
            return Response({
                'error': 'Wallet not found. Please contact support.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Candidate.DoesNotExist:
        return Response({
            'error': 'Candidate not found'
        }, status=status.HTTP_404_NOT_FOUND)
        
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unlocked_candidates(request):
    """Get list of unlocked candidates with full data for HR user"""
    
    if request.user.role != 'hr':
        return Response({
            'error': 'Only HR users can access this'
        }, status=status.HTTP_403_FORBIDDEN)
    
    unlocked_histories = UnlockHistory.objects.filter(
        hr_user=request.user.hr_profile
    ).select_related('candidate')
    
    unlocked_candidates = []
    for history in unlocked_histories:
        candidate = history.candidate
        serializer = FullCandidateSerializer(candidate)
        candidate_data = serializer.data
        candidate_data['credits_used'] = history.credits_used
        unlocked_candidates.append(candidate_data)
    
    return Response({
        'success': True,
        'unlocked_candidates': unlocked_candidates
    })
    
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_candidate_profile(request):
    """Get candidate's own profile"""
    
    if request.user.role != 'candidate':
        return Response({
            'error': 'Only candidates can access this'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        candidate = Candidate.objects.get(user=request.user)
        serializer = FullCandidateSerializer(candidate, context={'request': request})  
        return Response(serializer.data)
    except Candidate.DoesNotExist:
        return Response({
            'error': 'Profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def update_candidate_profile(request):
    """Update candidate's own profile"""
    
    if request.user.role != 'candidate':
        return Response({
            'error': 'Only candidates can update their profile'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        candidate = Candidate.objects.get(user=request.user)
        
        # Handle work experience if provided
        work_experience_data = request.data.get('work_experiences')
        career_gaps_data = request.data.get('career_gaps')

        if work_experience_data:
            candidate.work_experiences.all().delete()

            try:
                import json
                work_exp_list = json.loads(work_experience_data)

                print("=" * 80)
                print("WORK EXPERIENCES RECEIVED:")
                print(json.dumps(work_exp_list, indent=2))
                print("=" * 80)

                for i, exp_data in enumerate(work_exp_list, 1):
                    print(f"\n--- Creating Work Experience #{i} ---")
                    print(f"Company: {exp_data.get('company_name')}")
                    print(f"Role: {exp_data.get('role_title')}")

                    WorkExperience.objects.create(
                        candidate=candidate,
                        company_name=exp_data.get('company_name', ''),
                        role_title=exp_data.get('role_title', ''),
                        start_date=f"{exp_data.get('start_year')}-{_month_to_number(exp_data.get('start_month'))}-01",
                        end_date=f"{exp_data.get('end_year')}-{_month_to_number(exp_data.get('end_month'))}-01" if not exp_data.get('is_current') and exp_data.get('end_year') else None,
                        is_current=exp_data.get('is_current', False),
                        current_ctc=float(exp_data.get('ctc')) if exp_data.get('ctc') and exp_data.get('ctc').strip() else None,
                        location=exp_data.get('location', ''),
                        description=exp_data.get('description', ''),
                    )
                    print(f"✅ Saved work experience: {exp_data.get('company_name')}")

            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing error: {e}")
                print(f"Raw data: {work_experience_data}")
            except Exception as e:
                print(f"❌ Work experience error: {e}")
                import traceback
                traceback.print_exc()

        # Handle career gaps if provided
        if career_gaps_data:
            candidate.career_gaps.all().delete()

            try:
                import json
                career_gaps_list = json.loads(career_gaps_data)

                print("=" * 80)
                print("CAREER GAPS RECEIVED:")
                print(json.dumps(career_gaps_list, indent=2))
                print("=" * 80)

                for i, gap_data in enumerate(career_gaps_list, 1):
                    print(f"\n--- Creating Career Gap #{i} ---")
                    print(f"Gap Reason: {gap_data.get('gap_reason')}")

                    CareerGap.objects.create(
                        candidate=candidate,
                        start_date=f"{gap_data.get('start_year')}-{_month_to_number(gap_data.get('start_month'))}-01",
                        end_date=f"{gap_data.get('end_year')}-{_month_to_number(gap_data.get('end_month'))}-01",
                        gap_reason=gap_data.get('gap_reason', '')
                    )
                    print(f"✅ Saved career gap: {gap_data.get('gap_reason')}")

            except json.JSONDecodeError as e:
                print(f"❌ Career gaps JSON parsing error: {e}")
                print(f"Raw data: {career_gaps_data}")
            except Exception as e:
                print(f"❌ Career gaps error: {e}")
                import traceback
                traceback.print_exc()

        # Handle education if provided  
        education_data = request.data.get('educations')
        if education_data:
            candidate.educations.all().delete()
            
            try:
                import json
                
                # ✅ DIRECTLY PARSE JSON - NO REGEX CLEANING
                edu_list = json.loads(education_data)
                
                for edu_data in edu_list:
                    Education.objects.create(
                        candidate=candidate,
                        institution_name=edu_data.get('school', ''),
                        degree=edu_data.get('degree', ''),
                        field_of_study=edu_data.get('field', ''),
                        start_year=int(edu_data.get('start_year', 2020)),
                        end_year=int(edu_data.get('end_year', 2024)),
                        is_ongoing=False,
                        grade_percentage=float(edu_data.get('grade', '0').replace('%', '')) if edu_data.get('grade') else None,
                        location=edu_data.get('location', '')
                    )
            except Exception as e:
                print(f"Education parsing error: {e}")
        
        # Handle certifications if provided
        certifications_data = request.data.get('certifications')
        if certifications_data:
            candidate.certifications.all().delete()

            try:
                import json
                cert_list = json.loads(certifications_data)

                for i, cert_data in enumerate(cert_list):
                    Certification.objects.create(
                        candidate=candidate,
                        certification_name=cert_data.get('certification_name', ''),
                        issuing_organization=cert_data.get('issuing_organization', ''),
                        issue_date=cert_data.get('issue_date', ''),
                        document=request.FILES.get(f'certification_doc_{i}'),
                    )
            except Exception as e:
                print(f"Certifications parsing error: {e}")

        # Remove work_experiences, career_gaps, educations and certifications from request.data for candidate update
        candidate_data = request.data.copy()
        candidate_data.pop('work_experiences', None)
        candidate_data.pop('career_gaps', None)
        candidate_data.pop('educations', None)
        candidate_data.pop('certifications', None)
        
        # Use the same serializer with the same validation logic
        serializer = CandidateRegistrationSerializer(
            candidate, 
            data=candidate_data, 
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            
            response_serializer = FullCandidateSerializer(candidate, context={'request': request})
            return Response({
                'success': True,
                'message': 'Profile updated successfully',
                'profile': response_serializer.data
            })
        else:
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Candidate.DoesNotExist:
        return Response({
            'error': 'Profile not found'
        }, status=status.HTTP_404_NOT_FOUND)


def _month_to_number(month_name):
    """Convert month name to number"""
    if not month_name:  # ✅ Handle None, empty string
        return '01'
    months = {
        'January': '01', 'February': '02', 'March': '03', 'April': '04',
        'May': '05', 'June': '06', 'July': '07', 'August': '08',
        'September': '09', 'October': '10', 'November': '11', 'December': '12'
    }
    return months.get(month_name, '01')

def _safe_date_string(year, month_name, default_day='01'):
    """Safely construct date string, returns None if year is invalid"""
    if not year or year == 'null' or year == '':
        return None
    
    try:
        year_int = int(year)
        month_num = _month_to_number(month_name)
        return f"{year_int}-{month_num}-{default_day}"
    except (ValueError, TypeError):
        return None    
    
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_filter_options(request):
    """Get all filter options for candidate filtering"""
    
    if request.user.role != 'hr':
        return Response({
            'error': 'Only HR users can access this'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from .models import FilterCategory, FilterOption
    
    filter_type = request.query_params.get('type')
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    search = request.query_params.get('search', '')
    
    # Get unlocked candidate IDs for current HR user
    unlocked_ids = set(UnlockHistory.objects.filter(
        hr_user=request.user.hr_profile
    ).values_list('candidate_id', flat=True))
    
    # Map filter_type to correct field name
    field_mapping = {
        'department': 'role',
        'religion': 'religion', 
        'country': 'country',
        'state': 'state',
        'city': 'city',
        'display_order':'display_order'
    }
    
    if filter_type and filter_type != 'all':
        # Get specific filter category options with subcategories
        try:
            category = FilterCategory.objects.get(slug=filter_type, is_active=True)
            queryset = FilterOption.objects.filter(category=category, is_active=True,is_approved=True).order_by('display_order', 'name')
            
            if search:
                queryset = queryset.filter(name__icontains=search)
            
            # Get all options with their subcategories
            all_options = list(queryset)
            
            # Paginate
            total = len(all_options)
            start = (page - 1) * page_size
            end = start + page_size
            paginated_options = all_options[start:end]
            total_pages = (total + page_size - 1) // page_size
            
            base_url = f"/api/candidates/filter-options/?type={filter_type}&page_size={page_size}"
            if search:
                base_url += f"&search={search}"
                
            next_url = f"{base_url}&page={page + 1}" if page < total_pages else None
            previous_url = f"{base_url}&page={page - 1}" if page > 1 else None
            
            field_name = field_mapping.get(filter_type)
            
            results = []
            for option in paginated_options:
                if field_name:
                    total_count = Candidate.objects.filter(
                        is_active=True,
                        **{f"{field_name}": option}
                    ).count()
                    
                    unlocked_count = Candidate.objects.filter(
                        is_active=True,
                        id__in=unlocked_ids,
                        **{f"{field_name}": option}
                    ).count()
                    
                    locked_count = total_count - unlocked_count
                else:
                    total_count = unlocked_count = locked_count = 0
                
                # Get subcategories (children) if any
                subcategories = []
                for child in FilterOption.objects.filter(parent=option, is_active=True).order_by('display_order', 'name'):
                    if field_name:
                        child_total = Candidate.objects.filter(
                            is_active=True,
                            **{f"{field_name}": child}
                        ).count()
                        
                        child_unlocked = Candidate.objects.filter(
                            is_active=True,
                            id__in=unlocked_ids,
                            **{f"{field_name}": child}
                        ).count()
                        
                        child_locked = child_total - child_unlocked
                    else:
                        child_total = child_unlocked = child_locked = 0
                    
                    subcategories.append({
                        'value': child.name,
                        'label': child.name,
                        'count': child_total,
                        'unlocked_count': child_unlocked,
                        'locked_count': child_locked
                    })
                
                results.append({
                    'value': option.name,
                    'label': option.name,
                    'count': total_count,
                    'unlocked_count': unlocked_count,
                    'locked_count': locked_count,
                    'subcategories': subcategories
                })
            
            return Response({
                'count': total,
                'next': next_url,
                'previous': previous_url,
                'results': results
            })
        except FilterCategory.DoesNotExist:
            return Response({'error': 'Invalid filter type'}, status=400)
    
    # Return all categories with their subcategories and counts
    all_categories = FilterCategory.objects.filter(is_active=True).order_by('display_order', 'name')
    
    results = {}
    
    # Add "all" option showing total counts across all categories
    total_candidates = Candidate.objects.filter(is_active=True).count()
    total_unlocked = Candidate.objects.filter(is_active=True, id__in=unlocked_ids).count()
    total_locked = total_candidates - total_unlocked
    
    results['all'] = {
        'total_count': sum(FilterOption.objects.filter(category=cat, is_active=True).count() for cat in all_categories),
        'name': 'All Categories',
        'icon': None,
        'candidate_count': total_candidates,
        'unlocked_count': total_unlocked,
        'locked_count': total_locked,
        'subcategories': {}
    }
    
    # Add each category with subcategories
    for category in all_categories:
        options_count = FilterOption.objects.filter(category=category, is_active=True).count()
        icon_url = None
        if category.icon:
            icon_url = request.build_absolute_uri(category.icon.url)
        
        field_name = field_mapping.get(category.slug)
        
        # Get total candidates for this category
        if field_name:
            category_candidates = Candidate.objects.filter(
                is_active=True,
                **{f"{field_name}__isnull": False}
            ).count()
            
            category_unlocked = Candidate.objects.filter(
                is_active=True,
                id__in=unlocked_ids,
                **{f"{field_name}__isnull": False}
            ).count()
        else:
            category_candidates = 0
            category_unlocked = 0
        
        category_locked = category_candidates - category_unlocked
        
        # Get subcategories with counts
        subcategories = {}
        for option in FilterOption.objects.filter(category=category, is_active=True).order_by('display_order', 'name'):
            if field_name:
                option_total = Candidate.objects.filter(
                    is_active=True,
                    **{f"{field_name}": option}
                ).count()
                
                option_unlocked = Candidate.objects.filter(
                    is_active=True,
                    id__in=unlocked_ids,
                    **{f"{field_name}": option}
                ).count()
                
                option_locked = option_total - option_unlocked
            else:
                option_total = option_unlocked = option_locked = 0
            
            subcategories[option.slug] = {
                'name': option.name,
                'candidate_count': option_total,
                'unlocked_count': option_unlocked,
                'locked_count': option_locked
            }
        
        results[category.slug] = {
            'total_count': options_count,
            'name': category.name,
            'icon': icon_url,
            'candidate_count': category_candidates,
            'unlocked_count': category_unlocked,
            'locked_count': category_locked,
            'subcategories': subcategories
        }
        
        # Add subcategories to "all" option
        results['all']['subcategories'][category.slug] = {
            'name': category.name,
            'icon': icon_url,
            'candidate_count': category_candidates,
            'unlocked_count': category_unlocked,
            'locked_count': category_locked,
            'options': subcategories
        }
    
    return Response({'results': results})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_filter_categories(request):
    """Get all filter categories with subcategories and candidate counts"""

    if request.user.role != 'hr':
        return Response({
            'error': 'Only HR users can access this'
        }, status=status.HTTP_403_FORBIDDEN)

    from .models import FilterCategory, FilterOption
    from django.core.paginator import Paginator

    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    subcategory_page = int(request.query_params.get('subcategory_page', 1))
    subcategory_limit = int(request.query_params.get('subcategory_limit', 20))

    categories = FilterCategory.objects.filter(is_active=True).order_by('display_order', 'name')
    paginator = Paginator(categories, page_size)
    categories_page = paginator.get_page(page)
    
    field_mapping = {
        'department': 'role',
        'religion': 'religion', 
        'country': 'country',
        'state': 'state',
        'city': 'city'
    }
    
    unlocked_ids = set(UnlockHistory.objects.filter(
        hr_user=request.user.hr_profile
    ).values_list('candidate_id', flat=True))

    results = []

    for category in categories_page:
        icon_url = None
        if category.icon:
            icon_url = request.build_absolute_uri(category.icon.url)
        
        field_name = field_mapping.get(category.slug)
        
        if category.slug in ['state', 'city']:
            options = FilterOption.objects.filter(
                category=category,
                is_active=True
            ).order_by('display_order', 'name')
        else:
            options = FilterOption.objects.filter(
                category=category,
                is_active=True,
                parent__isnull=True
            ).order_by('display_order', 'name')

        # Paginate subcategories
        subcategory_paginator = Paginator(options, subcategory_limit)
        subcategory_page_obj = subcategory_paginator.get_page(subcategory_page)

        subcategories = []

        for option in subcategory_page_obj:
            if field_name:
                total_count = Candidate.objects.filter(
                    is_active=True,
                    **{f"{field_name}": option}
                ).count()
                
                unlocked_count = Candidate.objects.filter(
                    is_active=True,
                    id__in=unlocked_ids,
                    **{f"{field_name}": option}
                ).count()
                
                locked_count = total_count - unlocked_count
            else:
                total_count = unlocked_count = locked_count = 0
            
            children = FilterOption.objects.filter(
                parent=option, 
                is_active=True
            ).order_by('display_order', 'name')
            
            child_subcategories = []
            
            for child in children:
                if field_name:
                    child_total = Candidate.objects.filter(
                        is_active=True,
                        **{f"{field_name}": child}
                    ).count()
                    
                    child_unlocked = Candidate.objects.filter(
                        is_active=True,
                        id__in=unlocked_ids,
                        **{f"{field_name}": child}
                    ).count()
                    
                    child_locked = child_total - child_unlocked
                else:
                    child_total = child_unlocked = child_locked = 0
                
                # Get icon URL for child subcategory
                child_icon_url = None
                if child.icon:
                    child_icon_url = request.build_absolute_uri(child.icon.url)

                child_subcategories.append({
                    'id': str(child.id),
                    'name': child.name,
                    'slug': child.slug,
                    'icon': child_icon_url,
                    'total_candidates': child_total,
                    'locked_candidates': child_locked,
                    'unlocked_candidates': child_unlocked
                })
            
            # Get icon URL for subcategory
            option_icon_url = None
            if option.icon:
                option_icon_url = request.build_absolute_uri(option.icon.url)

            subcategories.append({
                'id': str(option.id),
                'name': option.name,
                'slug': option.slug,
                'icon': option_icon_url,
                'total_candidates': total_count,
                'locked_candidates': locked_count,
                'unlocked_candidates': unlocked_count,
                'children': child_subcategories
            })
        
        # Build subcategory pagination URLs
        subcategory_next = None
        subcategory_previous = None

        if subcategory_page_obj.has_next():
            subcategory_next = f"/api/candidates/filter-categories/?page={page}&page_size={page_size}&subcategory_page={subcategory_page_obj.next_page_number()}&subcategory_limit={subcategory_limit}"

        if subcategory_page_obj.has_previous():
            subcategory_previous = f"/api/candidates/filter-categories/?page={page}&page_size={page_size}&subcategory_page={subcategory_page_obj.previous_page_number()}&subcategory_limit={subcategory_limit}"

        results.append({
            'id': str(category.id),
            'name': category.name,
            'slug': category.slug,
            'icon': icon_url,
            'display_order': category.display_order,
            'is_active': category.is_active,
            'bento_grid': category.bento_grid,
            'dashboard_display': category.dashboard_display,
            'inner_filter': category.inner_filter,
            'subcategories': subcategories,
            'subcategory_count': subcategory_paginator.count,
            'subcategory_next': subcategory_next,
            'subcategory_previous': subcategory_previous
        })

    next_url = None
    previous_url = None

    if categories_page.has_next():
        next_url = f"/api/candidates/filter-categories/?page={categories_page.next_page_number()}&page_size={page_size}"

    if categories_page.has_previous():
        previous_url = f"/api/candidates/filter-categories/?page={categories_page.previous_page_number()}&page_size={page_size}"

    return Response({
        'success': True,
        'count': paginator.count,
        'next': next_url,
        'previous': previous_url,
        'filter_categories': results
    })

# ========== Notes & Followups APIs ==========

@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def add_candidate_note(request, candidate_id, note_id=None):
    """Add or delete note for a candidate - For HR users"""

    if request.user.role != 'hr':
        return Response({
            'error': 'Only HR users can manage notes'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        candidate = Candidate.objects.get(id=candidate_id, is_active=True)

        # Check if HR has unlocked this candidate
        if not UnlockHistory.objects.filter(hr_user=request.user.hr_profile, candidate=candidate).exists():
            return Response({
                'error': 'Candidate must be unlocked to manage notes'
            }, status=status.HTTP_403_FORBIDDEN)

        # DELETE: Remove note
        if request.method == 'DELETE':
            if not note_id:
                return Response({
                    'error': 'Note ID is required for deletion'
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                note = CandidateNote.objects.get(
                    id=note_id,
                    hr_user=request.user.hr_profile,
                    candidate=candidate
                )
                note.delete()
                return Response({
                    'success': True,
                    'message': 'Note deleted successfully'
                })
            except CandidateNote.DoesNotExist:
                return Response({
                    'error': 'Note not found'
                }, status=status.HTTP_404_NOT_FOUND)

        # POST: Add note
        serializer = CandidateNoteSerializer(data=request.data)
        if serializer.is_valid():
            note = serializer.save(
                hr_user=request.user.hr_profile,
                candidate=candidate
            )
            return Response({
                'success': True,
                'message': 'Note added successfully',
                'note': CandidateNoteSerializer(note).data
            })
        else:
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    except Candidate.DoesNotExist:
        return Response({
            'error': 'Candidate not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def add_candidate_followup(request, candidate_id, followup_id=None):
    """Add or delete followup for a candidate - For HR users"""

    if request.user.role != 'hr':
        return Response({
            'error': 'Only HR users can manage followups'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        candidate = Candidate.objects.get(id=candidate_id, is_active=True)

        # Check if HR has unlocked this candidate
        if not UnlockHistory.objects.filter(hr_user=request.user.hr_profile, candidate=candidate).exists():
            return Response({
                'error': 'Candidate must be unlocked to manage followups'
            }, status=status.HTTP_403_FORBIDDEN)

        # DELETE: Remove followup
        if request.method == 'DELETE':
            if not followup_id:
                return Response({
                    'error': 'Followup ID is required for deletion'
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                followup = CandidateFollowup.objects.get(
                    id=followup_id,
                    hr_user=request.user.hr_profile,
                    candidate=candidate
                )
                followup.delete()
                return Response({
                    'success': True,
                    'message': 'Followup deleted successfully'
                })
            except CandidateFollowup.DoesNotExist:
                return Response({
                    'error': 'Followup not found'
                }, status=status.HTTP_404_NOT_FOUND)

        # POST: Add followup
        serializer = CandidateFollowupSerializer(data=request.data)
        if serializer.is_valid():
            followup = serializer.save(
                hr_user=request.user.hr_profile,
                candidate=candidate
            )
            return Response({
                'success': True,
                'message': 'Followup added successfully',
                'followup': CandidateFollowupSerializer(followup).data
            })
        else:
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    except Candidate.DoesNotExist:
        return Response({
            'error': 'Candidate not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_candidate_notes_followups(request, candidate_id):
    """Get notes and followups for a candidate - For HR users"""
    
    if request.user.role != 'hr':
        return Response({
            'error': 'Only HR users can access this'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        candidate = Candidate.objects.get(id=candidate_id, is_active=True)
        
        # Check if HR has unlocked this candidate
        if not UnlockHistory.objects.filter(hr_user=request.user.hr_profile, candidate=candidate).exists():
            return Response({
                'error': 'Candidate must be unlocked to view notes and followups'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get notes and followups for this HR user and candidate
        notes = CandidateNote.objects.filter(
            hr_user=request.user.hr_profile,
            candidate=candidate
        )
        followups = CandidateFollowup.objects.filter(
            hr_user=request.user.hr_profile,
            candidate=candidate
        )
        
        return Response({
            'success': True,
            'notes': CandidateNoteSerializer(notes, many=True).data,
            'followups': CandidateFollowupSerializer(followups, many=True).data
        })
        
    except Candidate.DoesNotExist:
        return Response({
            'error': 'Candidate not found'
        }, status=status.HTTP_404_NOT_FOUND)
    


@api_view(['POST', 'PATCH'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def save_candidate_step(request):
    """Save candidate profile step-by-step (auto-save)"""
    
    if request.user.role != 'candidate':
        return Response({'error': 'Only candidates can save profile steps'}, status=403)
    
    step = request.data.get('step')
    if not step or int(step) not in [1, 2, 3, 4]:
        return Response({'error': 'Invalid step. Must be 1, 2, 3, or 4'}, status=400)
    
    step = int(step)
    is_final_submit = request.data.get('is_final_submit', 'false').lower() == 'true'

    try:
        candidate, created = Candidate.objects.get_or_create(
            user=request.user,
            defaults={
                'first_name': '',
                'last_name': '',
                'phone': '',
                'age': 0,
                'experience_years': 0,
                'skills': '',
                'profile_step': step
            }
        )
        
        # Get or create profile reminder tracker
        reminder, reminder_created = ProfileStepReminder.objects.get_or_create(
            user=request.user,
            defaults={'current_step': step}
        )
        
        # Update step progress
        old_step = reminder.current_step
        if step > old_step:
            reminder.update_step(step)
            print(f'[DEBUG] Updated profile step from {old_step} to {step} for {request.user.email}')
        
        update_data = {'profile_step': step}
        
        # ========== STEP 1: Personal Information ==========
        if step == 1:
            # Basic fields
            if request.data.get('first_name'):
                update_data['first_name'] = request.data.get('first_name')
            if request.data.get('last_name'):
                update_data['last_name'] = request.data.get('last_name')
            if request.data.get('phone'):
                update_data['phone'] = request.data.get('phone')
            if request.data.get('age'):
                update_data['age'] = int(request.data.get('age'))
            if request.data.get('current_ctc'):
                update_data['current_ctc'] = float(request.data.get('current_ctc'))
            if request.data.get('expected_ctc'):
                update_data['expected_ctc'] = float(request.data.get('expected_ctc'))
            if request.data.get('languages'):
                update_data['languages'] = request.data.get('languages')
            if request.data.get('street_address'):
                update_data['street_address'] = request.data.get('street_address')
            if request.data.get('willing_to_relocate') is not None:
                update_data['willing_to_relocate'] = request.data.get('willing_to_relocate') == 'true' or request.data.get('willing_to_relocate') == True
            if request.data.get('career_objective'):
                update_data['career_objective'] = request.data.get('career_objective')
            if request.data.get('joining_availability'):
                update_data['joining_availability'] = request.data.get('joining_availability')
            if request.data.get('notice_period_details'):
                update_data['notice_period_details'] = request.data.get('notice_period_details')

            # Mark step 1 as completed
            if not candidate.step1_completed:
                update_data['step1_completed'] = True
                update_data['step1_completed_at'] = timezone.now()

            # ========== HANDLE ROLE ==========
            role_value = request.data.get('role')
            if role_value:
                dept_category, _ = FilterCategory.objects.get_or_create(
                    slug='department',
                    defaults={'name': 'Department', 'display_order': 1}
                )
                role_slug = role_value.lower().replace(' ', '-')
                
                # Try to get existing approved role
                role = FilterOption.objects.filter(
                    category=dept_category,
                    slug=role_slug,
                    # is_approved=True
                ).first()
                
                if not role:
                    # Role doesn't exist, check if custom or predefined
                    other_option = FilterOption.objects.filter(
                        category=dept_category,
                        name__iexact='other',
                        is_approved=True
                    ).first()
                    
                    if other_option and role_value.lower() != 'other':
                        # Custom role - needs approval
                        role = FilterOption.objects.create(
                            category=dept_category,
                            slug=role_slug,
                            name=role_value,
                            is_active=False,
                            is_approved=False,
                            submitted_by=request.user,
                            submitted_at=timezone.now()
                        )
                    else:
                        # Pre-defined role - auto approve
                        role = FilterOption.objects.create(
                            category=dept_category,
                            slug=role_slug,
                            name=role_value,
                            is_active=True,
                            is_approved=True
                        )
                
                if role:
                    update_data['role'] = role

            # ========== HANDLE RELIGION ==========
            religion_value = request.data.get('religion')
            if religion_value:
                religion_category, _ = FilterCategory.objects.get_or_create(
                    slug='religion',
                    defaults={'name': 'Religion', 'display_order': 2}
                )
                religion_slug = religion_value.lower().replace(' ', '-')
                
                # Try to get existing approved religion
                religion = FilterOption.objects.filter(
                    category=religion_category,
                    slug=religion_slug,
                    # is_approved=True
                ).first()
                
                if not religion:
                    # Religion doesn't exist, check if custom or predefined
                    other_option = FilterOption.objects.filter(
                        category=religion_category,
                        name__iexact='other',
                        is_approved=True
                    ).first()
                    
                    if other_option and religion_value.lower() != 'other':
                        # Custom religion - needs approval
                        religion = FilterOption.objects.create(
                            category=religion_category,
                            slug=religion_slug,
                            name=religion_value,
                            is_active=False,
                            is_approved=False,
                            submitted_by=request.user,
                            submitted_at=timezone.now()
                        )
                    else:
                        # Pre-defined religion - auto approve
                        religion = FilterOption.objects.create(
                            category=religion_category,
                            slug=religion_slug,
                            name=religion_value,
                            is_active=True,
                            is_approved=True
                        )
                
                if religion:
                    update_data['religion'] = religion

            # ========== HANDLE LOCATION ==========
            state_value = request.data.get('state')
            city_value = request.data.get('city')
            
            if state_value or city_value:
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
                
                # Country is always India
                country, _ = FilterOption.objects.get_or_create(
                    category=country_category,
                    slug='india',
                    defaults={'name': 'India', 'is_active': True, 'is_approved': True}
                )
                update_data['country'] = country
                
                if state_value:
                    state_slug = state_value.lower().replace(' ', '-')
                    
                    # Try to get existing approved state
                    state = FilterOption.objects.filter(
                        category=state_category,
                        slug=state_slug,
                        is_approved=True
                    ).first()
                    
                    if not state:
                        # State doesn't exist, check if custom or predefined
                        other_option = FilterOption.objects.filter(
                            category=state_category,
                            name__iexact='other',
                            is_approved=True
                        ).first()
                        
                        if other_option and state_value.lower() != 'other':
                            # Custom state - needs approval
                            state = FilterOption.objects.create(
                                category=state_category,
                                slug=state_slug,
                                name=state_value.title(),
                                parent=country,
                                is_active=False,
                                is_approved=False,
                                submitted_by=request.user,
                                submitted_at=timezone.now()
                            )
                        else:
                            # Pre-defined state - auto approve
                            state = FilterOption.objects.create(
                                category=state_category,
                                slug=state_slug,
                                name=state_value.title(),
                                parent=country,
                                is_active=True,
                                is_approved=True
                            )
                    
                    if state:
                        update_data['state'] = state
                        
                        if city_value:
                            city_slug = f"{state_slug}-{city_value.lower().replace(' ', '-')}"
                            
                            # Try to get existing approved city
                            city = FilterOption.objects.filter(
                                category=city_category,
                                slug=city_slug,
                                is_approved=True
                            ).first()
                            
                            if not city:
                                # City doesn't exist, check if custom or predefined
                                other_option = FilterOption.objects.filter(
                                    category=city_category,
                                    name__iexact='other',
                                    is_approved=True
                                ).first()
                                
                                if other_option and city_value.lower() != 'other':
                                    # Custom city - needs approval
                                    city = FilterOption.objects.create(
                                        category=city_category,
                                        slug=city_slug,
                                        name=city_value.title(),
                                        parent=state,
                                        is_active=False,
                                        is_approved=False,
                                        submitted_by=request.user,
                                        submitted_at=timezone.now()
                                    )
                                else:
                                    # Pre-defined city - auto approve
                                    city = FilterOption.objects.create(
                                        category=city_category,
                                        slug=city_slug,
                                        name=city_value.title(),
                                        parent=state,
                                        is_active=True,
                                        is_approved=True
                                    )
                            
                            if city:
                                update_data['city'] = city
            
            # Handle profile image
            if 'profile_image' in request.FILES:
                update_data['profile_image'] = request.FILES['profile_image']
        
        # ========== STEP 2: Work Experience ==========
        elif step == 2:
            # Handle joining availability
            if request.data.get('joining_availability'):
                update_data['joining_availability'] = request.data.get('joining_availability')
            if request.data.get('notice_period_details'):
                update_data['notice_period_details'] = request.data.get('notice_period_details')

            work_experience_data = request.data.get('work_experience')
            if work_experience_data:
                candidate.work_experiences.all().delete()
                candidate.career_gaps.all().delete()

                import json
                work_exp_list = json.loads(work_experience_data)

                for exp_data in work_exp_list:
                    is_gap = exp_data.get('is_gap_period', False)

                    if is_gap:
                        start_year = exp_data.get('start_year')
                        start_month = exp_data.get('start_month')
                        end_year = exp_data.get('end_year')
                        end_month = exp_data.get('end_month')
                        
                        start_date = _safe_date_string(start_year, start_month)
                        end_date = _safe_date_string(end_year, end_month)
                        
                        if start_date and end_date:  # Only create if dates are valid
                            # Save as CareerGap
                            CareerGap.objects.create(
                                candidate=candidate,
                                start_date=start_date,
                                end_date=end_date,
                                gap_reason=exp_data.get('gap_reason', '')
                            )
                            print(f"✅ Saved career gap in step 2: {exp_data.get('gap_reason')}")
                    else:
                        start_year = exp_data.get('start_year')
                        start_month = exp_data.get('start_month')
                        end_year = exp_data.get('end_year')
                        end_month = exp_data.get('end_month')
                        is_current = exp_data.get('is_current', False)
                
                        start_date = _safe_date_string(start_year, start_month)
                
                        # Only construct end_date if NOT current and has valid year
                        end_date = None
                        if not is_current and end_year:
                            end_date = _safe_date_string(end_year, end_month)
                
                        if start_date:  # Only create if start_date is valid
                            # Save as WorkExperience
                            WorkExperience.objects.create(
                                candidate=candidate,
                                company_name=exp_data.get('company_name', ''),
                                role_title=exp_data.get('role_title', ''),
                                start_date=start_date,
                                end_date=end_date,
                                is_current=is_current,
                                current_ctc=float(exp_data.get('ctc', 0)) if exp_data.get('ctc') else None,
                                location=exp_data.get('location', ''),
                                description=exp_data.get('description', ''),
                        )
                        print(f"✅ Saved work experience in step 2: {exp_data.get('company_name')}")

            # Calculate experience
            from datetime import datetime
            total_months = 0
            for exp in candidate.work_experiences.all():
                start_date = exp.start_date
                end_date = exp.end_date if exp.end_date else datetime.now().date()
                
                months_diff = ((end_date.year - start_date.year) * 12) + (end_date.month - start_date.month)
                total_months += months_diff

            total_years = total_months // 12
            if total_years > 0:
                update_data['experience_years'] = total_years

            # Mark step 2 as completed
            if not candidate.step2_completed and candidate.work_experiences.exists():
                update_data['step2_completed'] = True
                update_data['step2_completed_at'] = timezone.now()
        
        # ========== STEP 3: Education + Skills ==========
        elif step == 3:
            if request.data.get('skills'):
                update_data['skills'] = request.data.get('skills')

            education_data = request.data.get('education')
            if education_data:
                candidate.educations.all().delete()

                import json
                edu_list = json.loads(education_data)

                for edu_data in edu_list:
                    Education.objects.create(
                        candidate=candidate,
                        institution_name=edu_data.get('school', ''),
                        degree=edu_data.get('degree', ''),
                        field_of_study=edu_data.get('field', ''),
                        start_year=int(edu_data.get('start_year', 2020)),
                        end_year=int(edu_data.get('end_year', 2024)),
                        is_ongoing=False,
                        grade_percentage=float(edu_data.get('grade', '0').replace('%', '')) if edu_data.get('grade') else None,
                        location=edu_data.get('location', '')
                    )

            # ✅ SAVE CERTIFICATIONS
            certifications_data = request.data.get('certifications')
            if certifications_data:
                candidate.certifications.all().delete()

                import json
                cert_list = json.loads(certifications_data)

                for i, cert_data in enumerate(cert_list):
                    Certification.objects.create(
                        candidate=candidate,
                        certification_name=cert_data.get('certification_name', ''),
                        issuing_organization=cert_data.get('issuing_organization', ''),
                        issue_date=cert_data.get('issue_date', ''),
                        document=request.FILES.get(f'certification_doc_{i}'),
                    )

            # Mark step 3 as completed
            if not candidate.step3_completed:
                update_data['step3_completed'] = True
                update_data['step3_completed_at'] = timezone.now()

        # ========== STEP 4: Documents ==========
        elif step == 4:
            # Resume/video upload — auto-save mein bhi ho sakta hai
            if 'resume' in request.FILES:
                update_data['resume'] = request.FILES['resume']
            if 'video_intro' in request.FILES:
                update_data['video_intro'] = request.FILES['video_intro']

            # Certifications — auto-save mein bhi save ho
            certifications_data = request.data.get('certifications')
            if certifications_data:
                candidate.certifications.all().delete()

                import json
                cert_list = json.loads(certifications_data)

                for i, cert_data in enumerate(cert_list):
                    Certification.objects.create(
                        candidate=candidate,
                        certification_name=cert_data.get('certification_name', ''),
                        issuing_organization=cert_data.get('issuing_organization', ''),
                        issue_date=cert_data.get('issue_date', ''),
                        document=request.FILES.get(f'certification_doc_{i}'),
                    )

            # Profile completion — sirf final submit pe
            if is_final_submit:
                has_agreed = request.data.get('has_agreed_to_declaration')
                if has_agreed == 'true' or has_agreed is True:
                    update_data['has_agreed_to_declaration'] = True
                    update_data['declaration_agreed_at'] = timezone.now()

                # Mark step 4 as completed
                if not candidate.step4_completed:
                    update_data['step4_completed'] = True
                    update_data['step4_completed_at'] = timezone.now()

                update_data['is_profile_completed'] = True
                reminder.is_profile_completed = True
                reminder.save()

                # Send notification
                try:
                    WorkfinaFCMService.send_to_user(
                        user=request.user,
                        title="🎉 Profile Completed!",
                        body="Great! Your profile is now complete. You're ready to connect with top recruiters!",
                        notification_type='COMPLETE_PROFILE',
                        data={
                            'profile_completed': True,
                            'step': step,
                            'action': 'profile_complete'
                        }
                    )
                except Exception as e:
                    print(f'[DEBUG] Failed to send notification: {str(e)}')
        
        # ========== UPDATE CANDIDATE ==========
        for field, value in update_data.items():
            setattr(candidate, field, value)
        candidate.save()
        
        serializer = FullCandidateSerializer(candidate, context={'request': request})
        
        return Response({
            'success': True,
            'message': f'Step {step} saved successfully',
            'current_step': candidate.profile_step,
            'is_completed': candidate.is_profile_completed,
            'profile': serializer.data
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': f'Failed to save step: {str(e)}'}, status=500)
    

@api_view(['GET'])
def get_public_filter_options(request):
    """Get department and religion options - publicly accessible"""
    
    from .models import FilterCategory, FilterOption
    
    try:
        dept_category = FilterCategory.objects.get(slug='department', is_active=True)
        religion_category = FilterCategory.objects.get(slug='religion', is_active=True)
        skills_category = FilterCategory.objects.get(slug='skills', is_active=True)
        languages_category = FilterCategory.objects.get(slug='languages', is_active=True)
        
        
        departments = FilterOption.objects.filter(
            category=dept_category, 
            is_active=True,
            is_approved=True
        ).order_by('display_order', 'name')
        
        religions = FilterOption.objects.filter(
            category=religion_category,
            is_active=True,
            is_approved=True
        ).order_by('display_order', 'name')

        skills = FilterOption.objects.filter(
            category=skills_category,
            is_active=True
        ).order_by('display_order', 'name')
        
        languages = FilterOption.objects.filter(
            category=languages_category,
            is_active=True,
            is_approved=True
        ).order_by('display_order', 'name')

        
        return Response({
            'success': True,
            'departments': [{'value': dept.slug, 'label': dept.name} for dept in departments],
            'religions': [{'value': relig.slug, 'label': relig.name} for relig in religions],
            'skills': [{'value': skill.slug, 'label': skill.name} for skill in skills],
            'languages': [{'value': lang.slug, 'label': lang.name} for lang in languages]
        })
        
    except FilterCategory.DoesNotExist:
        return Response({
            'success': True,
            'departments': [],
            'religions': [],
            'skills': [],
            'languages': []
        })
        
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_candidate_availability(request):
    """Get candidate's current availability status for hiring with dynamic UI configuration"""

    if request.user.role != 'candidate':
        return Response({
            'error': 'Only candidates can access this'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        candidate = Candidate.objects.get(user=request.user)

        # Check if we should show the prompt (show if date has changed)
        should_show_prompt = True
        if candidate.last_availability_update:
            import pytz
            ist = pytz.timezone('Asia/Kolkata')

            # Get current date in IST
            current_date = timezone.now().astimezone(ist).date()

            # Get last update date in IST
            last_update_date = candidate.last_availability_update.astimezone(ist).date()

            # Show prompt only if current date is different from last update date
            should_show_prompt = current_date != last_update_date

        # Get dynamic UI configuration from HiringAvailabilityUI model
        from apps.candidates.models import HiringAvailabilityUI
        ui_config = HiringAvailabilityUI.objects.filter(is_active=True).first()

        # Default UI configuration
        default_config = {
            'title': "Are you still available for hiring?",
            'message': "Please confirm if you're still open to new job opportunities.",
            'button_layout': 'column',
            'content_vertical_alignment': 'center',
            'background_type': 'color',
            'background_color': '#FFFFFF',
            'background_image': None,
            'gradient_start_color': '#FFFFFF',
            'gradient_end_color': '#F5F5F5',
            'icon': {
                'show': True,
                'source': 'material',
                'type': 'work_outline_rounded',
                'image_url': None,
                'size': 60.0,
                'color': '#4CAF50',
                'background_color': '#4CAF5019'
            },
            'title_style': {
                'font_size': 24.0,
                'font_weight': 'bold',
                'color': '#000000',
                'alignment': 'center'
            },
            'message_style': {
                'font_size': 16.0,
                'font_weight': 'normal',
                'color': '#757575',
                'alignment': 'center'
            },
            'primary_button': {
                'text': "Yes, I'm Available",
                'bg_color': '#4CAF50',
                'text_color': '#FFFFFF',
                'font_size': 18.0,
                'font_weight': 'w600',
                'height': 56.0,
                'border_radius': 12.0
            },
            'secondary_button': {
                'text': "No, Not Available",
                'bg_color': '#FFFFFF',
                'text_color': '#616161',
                'border_color': '#BDBDBD',
                'font_size': 18.0,
                'font_weight': 'w600',
                'height': 56.0,
                'border_radius': 12.0
            },
            'spacing': {
                'between_buttons': 16.0,
                'padding_horizontal': 24.0,
                'padding_vertical': 32.0
            },
            'extra_content': []
        }

        # If UI config exists, use it
        if ui_config:
            config_data = {
                'title': ui_config.title,
                'message': ui_config.message,
                'button_layout': ui_config.button_layout,
                'content_vertical_alignment': ui_config.content_vertical_alignment,
                'background_type': ui_config.background_type,
                'background_color': ui_config.background_color,
                'background_image': request.build_absolute_uri(ui_config.background_image.url) if ui_config.background_image else None,
                'gradient_start_color': ui_config.gradient_start_color,
                'gradient_end_color': ui_config.gradient_end_color,
                'icon': {
                    'show': ui_config.show_icon,
                    'source': ui_config.icon_source,
                    'type': ui_config.icon_type,
                    'image_url': request.build_absolute_uri(ui_config.icon_image.url) if ui_config.icon_image else None,
                    'size': ui_config.icon_size,
                    'color': ui_config.icon_color,
                    'background_color': ui_config.icon_background_color
                },
                'title_style': {
                    'font_size': ui_config.title_font_size,
                    'font_weight': ui_config.title_font_weight,
                    'color': ui_config.title_color,
                    'alignment': ui_config.title_alignment
                },
                'message_style': {
                    'font_size': ui_config.message_font_size,
                    'font_weight': ui_config.message_font_weight,
                    'color': ui_config.message_color,
                    'alignment': ui_config.message_alignment
                },
                'primary_button': {
                    'text': ui_config.primary_button_text,
                    'bg_color': ui_config.primary_button_bg_color,
                    'text_color': ui_config.primary_button_text_color,
                    'font_size': ui_config.primary_button_font_size,
                    'font_weight': ui_config.primary_button_font_weight,
                    'height': ui_config.primary_button_height,
                    'border_radius': ui_config.primary_button_border_radius
                },
                'secondary_button': {
                    'text': ui_config.secondary_button_text,
                    'bg_color': ui_config.secondary_button_bg_color,
                    'text_color': ui_config.secondary_button_text_color,
                    'border_color': ui_config.secondary_button_border_color,
                    'font_size': ui_config.secondary_button_font_size,
                    'font_weight': ui_config.secondary_button_font_weight,
                    'height': ui_config.secondary_button_height,
                    'border_radius': ui_config.secondary_button_border_radius
                },
                'spacing': {
                    'between_buttons': ui_config.spacing_between_buttons,
                    'padding_horizontal': ui_config.content_padding_horizontal,
                    'padding_vertical': ui_config.content_padding_vertical
                },
                'extra_content': ui_config.extra_content if ui_config.extra_content else []
            }
        else:
            config_data = default_config

        # Format last_availability_update to IST
        last_update_ist = None
        if candidate.last_availability_update:
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            last_update_ist = candidate.last_availability_update.astimezone(ist).strftime('%d %b %Y, %I:%M %p IST')

        return Response({
            'success': True,
            'is_available_for_hiring': candidate.is_available_for_hiring,
            'last_availability_update': last_update_ist,
            'should_show_prompt': should_show_prompt,
            'ui_config': config_data
        })
    except Candidate.DoesNotExist:
        return Response({
            'error': 'Profile not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_candidate_availability(request):
    """Update candidate's availability status for hiring"""

    if request.user.role != 'candidate':
        return Response({
            'error': 'Only candidates can update their availability'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        candidate = Candidate.objects.get(user=request.user)

        is_available = request.data.get('is_available_for_hiring')
        if is_available is None:
            return Response({
                'error': 'is_available_for_hiring field is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Convert to boolean
        if isinstance(is_available, str):
            is_available = is_available.lower() in ['true', '1', 'yes']

        # Store old availability status to check if it changed
        old_availability = candidate.is_available_for_hiring

        candidate.is_available_for_hiring = is_available
        candidate.last_availability_update = timezone.now()
        candidate.save()

        # If candidate marked themselves as NOT available (hired/unavailable)
        # Notify all recruiters who unlocked this candidate
        if old_availability and not is_available:
            try:
                # Get all HR users who unlocked this candidate
                unlocked_hrs = UnlockHistory.objects.filter(
                    candidate=candidate
                ).select_related('hr_user__user')

                # Send notification to each HR
                for unlock_history in unlocked_hrs:
                    hr_user = unlock_history.hr_user.user
                    try:
                        WorkfinaFCMService.send_to_user(
                            user=hr_user,
                            title="Candidate No Longer Available",
                            body=f"{candidate.masked_name} is no longer available for hiring opportunities.",
                            notification_type='CANDIDATE_UNAVAILABLE',
                            data={
                                'candidate_id': str(candidate.id),
                                'candidate_name': candidate.masked_name,
                                'is_available': False,
                                'action': 'candidate_unavailable'
                            }
                        )
                        print(f'[DEBUG] Sent unavailability notification to HR: {hr_user.email}')
                    except Exception as e:
                        print(f'[DEBUG] Failed to send notification to HR {hr_user.email}: {str(e)}')
            except Exception as e:
                print(f'[DEBUG] Error notifying HRs about candidate unavailability: {str(e)}')

        return Response({
            'success': True,
            'message': 'Availability status updated successfully',
            'is_available_for_hiring': candidate.is_available_for_hiring,
            'last_availability_update': candidate.last_availability_update
        })
    except Candidate.DoesNotExist:
        return Response({
            'error': 'Profile not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_candidate_hiring_status(request, candidate_id):
    """Update candidate hiring status (for HR users)"""
    
    if request.user.role != 'hr':
        return Response({
            'error': 'Only HR users can update hiring status'
        }, status=403)
    
    try:
        candidate = Candidate.objects.get(id=candidate_id, is_active=True)
        
        # Check if HR has unlocked this candidate
        if not UnlockHistory.objects.filter(hr_user=request.user.hr_profile, candidate=candidate).exists():
            return Response({
                'error': 'Candidate must be unlocked to update hiring status'
            }, status=403)
        
        new_status = request.data.get('status')
        company_name = request.data.get('company_name', '')
        position_title = request.data.get('position_title', '')
        notes = request.data.get('notes', '')
        
        if new_status not in ['HIRED', 'ON_HOLD', 'REJECTED', 'WITHDRAWN']:
            return Response({
                'error': 'Invalid status'
            }, status=400)
        
        # Update or create candidate status
        from notifications.models import CandidateStatus
        candidate_status, created = CandidateStatus.objects.update_or_create(
            candidate=candidate,
            defaults={
                'status': new_status,
                'updated_by': request.user.hr_profile,
                'company_name': company_name,
                'position_title': position_title,
                'notes': notes
            }
        )
        
        # Send notification to candidate about status update
        if new_status == 'HIRED':
            try:
                WorkfinaFCMService.send_to_user(
                    user=candidate.user,
                    title="🎉 Congratulations! You've been hired!",
                    body=f"Great news! You've been selected for {position_title} at {company_name}. Check your profile for details.",
                    notification_type='CANDIDATE_HIRED',
                    data={
                        'status': new_status,
                        'company_name': company_name,
                        'position_title': position_title,
                        'hr_company': request.user.hr_profile.company.name if request.user.hr_profile.company else "No Company"
                    }
                )
                print(f'[DEBUG] Sent hiring notification to candidate {candidate.user.email}')
            except Exception as e:
                print(f'[DEBUG] Failed to send hiring notification to candidate: {str(e)}')
            
            # Notify other HRs who unlocked this candidate
            try:
                WorkfinaFCMService.notify_hrs_about_hired_candidate(candidate)
                print(f'[DEBUG] Notified other HRs about hired candidate {candidate.masked_name}')
            except Exception as e:
                print(f'[DEBUG] Failed to notify HRs about hired candidate: {str(e)}')
        
        return Response({
            'success': True,
            'message': f'Candidate status updated to {new_status}',
            'status': new_status,
            'candidate': candidate.masked_name
        })
        
    except Candidate.DoesNotExist:
        return Response({
            'error': 'Candidate not found'
        }, status=404)        
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile_tips(request):
    """Get active profile tips for candidate dashboard"""
    
    if request.user.role != 'candidate':
        return Response({
            'error': 'Only candidates can access profile tips'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        tips = ProfileTip.objects.filter(is_active=True).order_by('display_order')
        
        tips_data = []
        for tip in tips:
            tips_data.append({
                'id': str(tip.id),
                'title': tip.title,
                'subtitle': tip.subtitle,
                'icon_type': tip.icon_type,
                'instructions': tip.instructions,
                'display_order': tip.display_order
            })
        
        return Response({
            'success': True,
            'tips': tips_data
        })

    except Exception as e:
        return Response({
            'error': f'Failed to load profile tips: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_countries(request):
    """
    Search countries for autocomplete/autosuggest
    Query params:
    - q: search query (required)
    - limit: number of results (optional, default 10)

    Returns:
    - Countries matching search query
    - Ordered by name
    """
    search_query = request.query_params.get('q', '').strip()
    limit = int(request.query_params.get('limit', 10))

    if not search_query:
        return Response({
            'success': False,
            'error': 'Search query (q) is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        country_category = FilterCategory.objects.get(slug='country')

        # Search countries by name (case-insensitive partial match)
        countries = FilterOption.objects.filter(
            category=country_category,
            name__icontains=search_query,
            is_active=True,
            is_approved=True
        ).order_by('name')[:limit]

        countries_data = [
            {
                'id': str(country.id),
                'name': country.name,
                'slug': country.slug
            }
            for country in countries
        ]

        return Response({
            'success': True,
            'query': search_query,
            'count': len(countries_data),
            'countries': countries_data
        })

    except FilterCategory.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Country category not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_states(request):
    """
    Search states for autocomplete/autosuggest
    Query params:
    - q: search query (required)
    - country: country ID (optional - filters states by country)
    - limit: number of results (optional, default 10)

    Returns:
    - States matching search query
    - Ordered by name
    """
    search_query = request.query_params.get('q', '').strip()
    country_id = request.query_params.get('country', '').strip()
    limit = int(request.query_params.get('limit', 10))

    if not search_query:
        return Response({
            'success': False,
            'error': 'Search query (q) is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        state_category = FilterCategory.objects.get(slug='state')

        # Build query
        query_filter = {
            'category': state_category,
            'name__icontains': search_query,
            'is_active': True,
            'is_approved': True
        }

        # Filter by country if provided
        if country_id:
            query_filter['parent_id'] = country_id

        # Search states by name (case-insensitive partial match)
        states = FilterOption.objects.filter(**query_filter).order_by('name')[:limit]

        states_data = [
            {
                'id': str(state.id),
                'name': state.name,
                'slug': state.slug,
                'country_id': str(state.parent_id) if state.parent_id else None
            }
            for state in states
        ]

        return Response({
            'success': True,
            'query': search_query,
            'count': len(states_data),
            'states': states_data
        })

    except FilterCategory.DoesNotExist:
        return Response({
            'success': False,
            'error': 'State category not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_cities(request):
    """
    Search cities for autocomplete/autosuggest
    Query params:
    - q: search query (required)
    - state: state ID (optional - filters cities by state)
    - limit: number of results (optional, default 10)

    Returns:
    - Cities matching search query
    - Ordered by name
    """
    search_query = request.query_params.get('q', '').strip()
    state_id = request.query_params.get('state', '').strip()
    limit = int(request.query_params.get('limit', 10))

    if not search_query:
        return Response({
            'success': False,
            'error': 'Search query (q) is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    if not state_id:
        return Response({
            'success': False,
            'error': 'State ID (state) is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        city_category = FilterCategory.objects.get(slug='city')

        # Build query
        query_filter = {
            'category': city_category,
            'name__icontains': search_query,
            'is_active': True,
            'is_approved': True
        }

        # Filter by state if provided
        if state_id:
            query_filter['parent_id'] = state_id

        # Search cities by name (case-insensitive partial match)
        cities = FilterOption.objects.filter(**query_filter).order_by('name')[:limit]

        cities_data = [
            {
                'id': str(city.id),
                'name': city.name,
                'slug': city.slug,
                'state_id': str(city.parent_id) if city.parent_id else None
            }
            for city in cities
        ]

        return Response({
            'success': True,
            'query': search_query,
            'count': len(cities_data),
            'cities': cities_data
        })

    except FilterCategory.DoesNotExist:
        return Response({
            'success': False,
            'error': 'City category not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_certification_document(request, certification_id):
    """Upload or remove document for a candidate's certification"""

    if request.user.role != 'candidate':
        return Response({
            'error': 'Only candidates can upload certification documents'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        certification = Certification.objects.get(
            id=certification_id,
            candidate__user=request.user
        )
    except Certification.DoesNotExist:
        return Response({
            'error': 'Certification not found'
        }, status=status.HTTP_404_NOT_FOUND)

    # DELETE: Remove document
    if request.method == 'DELETE':
        if certification.document:
            certification.document.delete(save=False)
        certification.document = None
        certification.save()
        return Response({
            'success': True,
            'message': 'Document removed successfully'
        })

    # POST: Upload document
    document = request.FILES.get('document')
    if not document:
        return Response({
            'error': 'No document provided. Send file with key "document"'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Delete old document if exists before saving new one
    if certification.document:
        certification.document.delete(save=False)

    certification.document = document
    certification.save()

    from .serializers import CertificationSerializer
    return Response({
        'success': True,
        'message': 'Document uploaded successfully',
        'certification': CertificationSerializer(certification, context={'request': request}).data
    })

