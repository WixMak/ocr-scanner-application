from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from app.imaging.page import WHITE_BGR, to_grayscale

MAX_ORB_FEATURES = 5000
LOWE_RATIO = 0.75
MIN_INLIER_MATCHES = 30
RANSAC_REPROJECTION_THRESHOLD_PX = 5.0


@dataclass(frozen=True)
class AlignmentResult:
    image: np.ndarray
    is_aligned: bool


@dataclass(frozen=True)
class PageFeatures:
    keypoints: Sequence[cv2.KeyPoint]
    descriptors: np.ndarray | None


@dataclass(frozen=True)
class _FeatureMatch:
    homography: np.ndarray
    inlier_count: int


def align_to_reference(scan: np.ndarray, reference: np.ndarray) -> AlignmentResult:
    """Warp a filled-in scan onto the blank template so template field boxes line up.

    Falls back to a plain resize when not enough printed features match.
    """
    reference_height, reference_width = reference.shape[:2]
    homography = _estimate_homography(scan, reference)
    if homography is None:
        resized = cv2.resize(scan, (reference_width, reference_height))
        return AlignmentResult(image=resized, is_aligned=False)
    warped = cv2.warpPerspective(
        scan, homography, (reference_width, reference_height), borderValue=WHITE_BGR
    )
    return AlignmentResult(image=warped, is_aligned=True)


def find_page_features(page: np.ndarray) -> PageFeatures:
    orb = cv2.ORB_create(nfeatures=MAX_ORB_FEATURES)
    keypoints, descriptors = orb.detectAndCompute(to_grayscale(page), None)
    return PageFeatures(keypoints=keypoints, descriptors=descriptors)


def count_shared_features(scan: PageFeatures, reference: PageFeatures) -> int:
    """How many printed features of the scan land in the same place on the reference page."""
    match = _match_features(scan, reference)
    return 0 if match is None else match.inlier_count


def _estimate_homography(scan: np.ndarray, reference: np.ndarray) -> np.ndarray | None:
    match = _match_features(find_page_features(scan), find_page_features(reference))
    if match is None or match.inlier_count < MIN_INLIER_MATCHES:
        return None
    return match.homography


def _match_features(scan: PageFeatures, reference: PageFeatures) -> _FeatureMatch | None:
    if scan.descriptors is None or reference.descriptors is None:
        return None

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    candidate_pairs = matcher.knnMatch(scan.descriptors, reference.descriptors, k=2)
    good_matches = [
        pair[0]
        for pair in candidate_pairs
        if len(pair) == 2 and pair[0].distance < LOWE_RATIO * pair[1].distance
    ]
    if len(good_matches) < MIN_INLIER_MATCHES:
        return None

    scan_points = np.float32([scan.keypoints[match.queryIdx].pt for match in good_matches])
    reference_points = np.float32(
        [reference.keypoints[match.trainIdx].pt for match in good_matches]
    )
    homography, inlier_mask = cv2.findHomography(
        scan_points, reference_points, cv2.RANSAC, RANSAC_REPROJECTION_THRESHOLD_PX
    )
    if homography is None:
        return None
    return _FeatureMatch(homography=homography, inlier_count=int(inlier_mask.sum()))
