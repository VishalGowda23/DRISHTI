"""
RiskLens AI — API Verification Dependencies
Provides dependencies for role validation and other security assertions.
"""

from fastapi import Header, HTTPException, status

def verify_cro_role(x_user_role: str = Header(default="TRADER")) -> str:
    """Validate that the user has elevated CRO or ADMIN privileges.
    
    Reads user role from X-User-Role HTTP header.
    """
    role = x_user_role.upper().strip()
    if role not in ("CRO", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Access denied. Only Chief Risk Officers (CRO) or ADMIN roles can modify risk limits."
        )
    return role
