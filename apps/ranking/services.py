"""
Ranking System Services
Contains core logic for calculating candidate scores and assigning credits
"""

from apps.ranking.models import RankingConfig, CandidateRank, RankingHistory, PointsCreditMapping


def calculate_candidate_score(candidate):
    """
    Calculate total score for a candidate based on RankingConfig

    Returns:
        tuple: (total_score, score_breakdown_dict)
    """

    # Get active config or use defaults
    config = RankingConfig.objects.filter(is_active=True).first()
    if not config:
        config = RankingConfig()

    score_breakdown = {
        'experience_score': 0,
        'education_score': 0,
        'certification_score': 0,
        'skills_score': 0,
        'profile_completeness_score': 0,
        'availability_score': 0,
        'verification_score': 0,
    }

    # ========== 1. EXPERIENCE SCORE ==========
    if candidate.experience_years:
        exp_score = candidate.experience_years * config.experience_points_per_year
        score_breakdown['experience_score'] = min(exp_score, config.max_experience_points)

    # ========== 2. EDUCATION SCORE ==========
    # Take highest degree
    educations = candidate.educations.all()
    education_points = 0

    for edu in educations:
        degree_lower = edu.degree.lower()

        if 'phd' in degree_lower or 'doctorate' in degree_lower or 'ph.d' in degree_lower:
            education_points = max(education_points, config.points_phd)
        elif 'master' in degree_lower or 'm.tech' in degree_lower or 'mba' in degree_lower or 'm.sc' in degree_lower or 'mca' in degree_lower:
            education_points = max(education_points, config.points_masters)
        elif 'bachelor' in degree_lower or 'b.tech' in degree_lower or 'bca' in degree_lower or 'b.sc' in degree_lower or 'b.e' in degree_lower or 'bba' in degree_lower:
            education_points = max(education_points, config.points_bachelors)
        elif 'diploma' in degree_lower or 'polytechnic' in degree_lower:
            education_points = max(education_points, config.points_diploma)
        elif '12th' in degree_lower or 'intermediate' in degree_lower or 'higher secondary' in degree_lower:
            education_points = max(education_points, config.points_12th)
        elif '10th' in degree_lower or 'matriculation' in degree_lower or 'secondary' in degree_lower:
            education_points = max(education_points, config.points_10th)

    score_breakdown['education_score'] = education_points

    # ========== 3. CERTIFICATION SCORE ==========
    cert_count = candidate.certifications.count()
    cert_score = cert_count * config.points_per_certification
    score_breakdown['certification_score'] = min(cert_score, config.max_certification_points)

    # ========== 4. SKILLS SCORE ==========
    skills_list = candidate.get_skills_list()
    skills_score = len(skills_list) * config.points_per_skill
    score_breakdown['skills_score'] = min(skills_score, config.max_skills_points)

    # ========== 5. PROFILE COMPLETENESS SCORE ==========
    completeness_score = 0

    if candidate.resume:
        completeness_score += config.points_resume_uploaded
    if candidate.video_intro:
        completeness_score += config.points_video_uploaded
    if candidate.profile_image:
        completeness_score += config.points_profile_image_uploaded
    if candidate.career_objective and candidate.career_objective.strip():
        completeness_score += config.points_career_objective_filled
    if candidate.is_profile_completed:
        completeness_score += config.points_all_steps_completed

    score_breakdown['profile_completeness_score'] = completeness_score

    # ========== 6. AVAILABILITY SCORE ==========
    availability_score = 0

    if candidate.joining_availability == 'IMMEDIATE':
        availability_score += config.points_immediate_joining
    if candidate.willing_to_relocate:
        availability_score += config.points_willing_to_relocate

    score_breakdown['availability_score'] = availability_score

    # ========== 7. VERIFICATION SCORE ==========
    if candidate.is_verified:
        score_breakdown['verification_score'] = config.points_verified_profile

    # ========== TOTAL SCORE ==========
    total_score = sum(score_breakdown.values())

    return total_score, score_breakdown


def get_credits_for_points(total_score):
    """
    Get credits required based on points using PointsCreditMapping

    Admin can define custom mappings in the admin panel.
    Returns highest matching tier credits (minimum 10 credits).

    Args:
        total_score: Total points scored by candidate

    Returns:
        int: credits_required
    """

    # Get all active mappings ordered by points descending
    mappings = PointsCreditMapping.objects.filter(
        is_active=True
    ).order_by('-points_threshold')

    # Find the highest matching tier
    for mapping in mappings:
        if total_score >= mapping.points_threshold:
            return mapping.credits_required

    # Default minimum credits if no mapping matches
    return 10


def update_candidate_rank(candidate, save_history=False):
    """
    Calculate and save rank for a candidate

    Args:
        candidate: Candidate instance
        save_history: Whether to save to RankingHistory (default: False)

    Returns:
        CandidateRank instance
    """

    total_score, breakdown = calculate_candidate_score(candidate)
    credits = get_credits_for_points(total_score)

    # Update or create rank record
    rank, created = CandidateRank.objects.update_or_create(
        candidate=candidate,
        defaults={
            'total_score': total_score,
            'experience_score': breakdown['experience_score'],
            'education_score': breakdown['education_score'],
            'certification_score': breakdown['certification_score'],
            'skills_score': breakdown['skills_score'],
            'profile_completeness_score': breakdown['profile_completeness_score'],
            'availability_score': breakdown['availability_score'],
            'verification_score': breakdown['verification_score'],
            'credits_required': credits,
        }
    )

    # Optionally save to history
    if save_history:
        RankingHistory.objects.create(
            candidate=candidate,
            total_score=total_score,
            credits_required=credits,
        )

    return rank


def recalculate_all_ranks(save_history=False):
    """
    Recalculate ranks for all active candidates

    Args:
        save_history: Whether to save each calculation to history

    Returns:
        int: Number of candidates processed
    """

    from apps.candidates.models import Candidate

    candidates = Candidate.objects.filter(is_active=True)
    count = 0

    # Calculate scores for all candidates
    for candidate in candidates:
        update_candidate_rank(candidate, save_history=save_history)
        count += 1

    return count


def get_candidate_rank_breakdown(candidate):
    """
    Get detailed rank breakdown for a candidate

    Returns:
        dict: Complete rank information including breakdown
    """

    try:
        rank = candidate.rank
        return {
            'total_score': rank.total_score,
            'credits_required': rank.credits_required,
            'last_calculated': rank.last_calculated,
            'breakdown': {
                'experience_score': rank.experience_score,
                'education_score': rank.education_score,
                'certification_score': rank.certification_score,
                'skills_score': rank.skills_score,
                'profile_completeness_score': rank.profile_completeness_score,
                'availability_score': rank.availability_score,
                'verification_score': rank.verification_score,
            }
        }
    except CandidateRank.DoesNotExist:
        # If no rank exists yet, calculate it
        update_candidate_rank(candidate)
        return get_candidate_rank_breakdown(candidate)
