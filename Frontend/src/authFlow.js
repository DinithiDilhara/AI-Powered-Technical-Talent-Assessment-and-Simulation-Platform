export function workspacePathFor(role, assessments = []) {
  if (role === 'employer') return '/dashboard';
  if (role !== 'candidate') return '/login';

  const assessment = assessments.find((item) => item.status === 'Published') || assessments[0];
  return assessment ? `/candidate/welcome/${encodeURIComponent(assessment.id)}` : '/';
}

export function employerRouteRedirect(user, assessments = []) {
  if (!user) return '/login';
  return user.role === 'employer' ? null : workspacePathFor(user.role, assessments);
}

export function candidateRouteRedirect(user, preview = false) {
  if (user?.role === 'employer') return '/dashboard';
  if (user?.role === 'candidate' || preview) return null;
  return '/login';
}
