from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from apps.ranking.models import RankingConfig
from apps.ranking.services import calculate_candidate_score


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ranking_points_breakdown(request):
    """
    API to show how ranking system works
    Returns all possible ways to earn points with current configuration
    """

    # Get active config
    config = RankingConfig.objects.filter(is_active=True).first()
    if not config:
        config = RankingConfig()

    # Get current candidate if exists
    candidate = None
    try:
        candidate = request.user.candidate_profile.first()
    except:
        pass

    # Calculate current scores if candidate exists
    current_scores = None
    if candidate:
        total_score, breakdown = calculate_candidate_score(candidate)
        current_scores = {
            'total_score': total_score,
            'breakdown': breakdown
        }

    # Build response with all point earning opportunities
    response_data = {
        'current_scores': current_scores,
        'how_to_earn_points': {
            'experience': {
                'title': 'Work Experience',
                'points_per_year': config.experience_points_per_year,
                'max_points': config.max_experience_points,
                'description': f'Earn {config.experience_points_per_year} points per year of experience (maximum {config.max_experience_points} points)',
                'example': f'5 years experience = {min(5 * config.experience_points_per_year, config.max_experience_points)} points'
            },
            'education': {
                'title': 'Education',
                'max_points': config.points_phd,
                'description': 'Points based on highest degree (only one counts)',
                'levels': [
                    {'degree': '10th', 'points': config.points_10th},
                    {'degree': '12th/Intermediate', 'points': config.points_12th},
                    {'degree': 'Diploma/Polytechnic', 'points': config.points_diploma},
                    {'degree': 'Bachelor\'s Degree', 'points': config.points_bachelors},
                    {'degree': 'Master\'s Degree', 'points': config.points_masters},
                    {'degree': 'PhD/Doctorate', 'points': config.points_phd},
                ]
            },
            'certifications': {
                'title': 'Certifications',
                'points_per_certification': config.points_per_certification,
                'max_points': config.max_certification_points,
                'description': f'Earn {config.points_per_certification} points per certification (maximum {config.max_certification_points} points)',
                'example': f'3 certifications = {min(3 * config.points_per_certification, config.max_certification_points)} points'
            },
            'skills': {
                'title': 'Skills',
                'points_per_skill': config.points_per_skill,
                'max_points': config.max_skills_points,
                'description': f'Earn {config.points_per_skill} point per skill added (maximum {config.max_skills_points} points)',
                'example': f'10 skills = {min(10 * config.points_per_skill, config.max_skills_points)} points'
            },
            'profile_completeness': {
                'title': 'Profile Completeness',
                'max_points': (config.points_resume_uploaded + config.points_video_uploaded +
                              config.points_profile_image_uploaded + config.points_career_objective_filled +
                              config.points_all_steps_completed),
                'description': 'Complete your profile to earn bonus points',
                'items': [
                    {'action': 'Upload Resume', 'points': config.points_resume_uploaded},
                    {'action': 'Upload Video Introduction', 'points': config.points_video_uploaded},
                    {'action': 'Upload Profile Image', 'points': config.points_profile_image_uploaded},
                    {'action': 'Fill Career Objective', 'points': config.points_career_objective_filled},
                    {'action': 'Complete All Profile Steps', 'points': config.points_all_steps_completed},
                ]
            },
            'availability': {
                'title': 'Availability Bonus',
                'max_points': config.points_immediate_joining + config.points_willing_to_relocate,
                'description': 'Show your flexibility to earn bonus points',
                'items': [
                    {'action': 'Immediate Joining Available', 'points': config.points_immediate_joining},
                    {'action': 'Willing to Relocate', 'points': config.points_willing_to_relocate},
                ]
            },
            'verification': {
                'title': 'Profile Verification',
                'points': config.points_verified_profile,
                'description': f'Get your profile verified by admin to earn {config.points_verified_profile} bonus points',
            }
        }
    }

    # Add summary (capped at 100 for display purposes)
    response_data['summary'] = {
        'max_possible_points': 100,
        'description': 'Maximum points you can earn by completing everything'
    }

    return Response(response_data, status=status.HTTP_200_OK)
