"""Fixed Deposits Service"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..error_handler import DataError
from ..logging_config import logger


def calculate_compound_interest(
    principal: float,
    annual_rate: float,
    time_in_years: float,
    compounding_frequency: int = 4
) -> float:
    """Calculate compound interest.
    
    Args:
        principal: Principal amount deposited
        annual_rate: Annual interest rate (as percentage, e.g., 7.5 for 7.5%)
        time_in_years: Time period in years
        compounding_frequency: Number of times interest is compounded per year (default: 4 for quarterly)
    
    Returns:
        Final amount after compound interest
    """
    if principal <= 0 or annual_rate <= 0 or time_in_years <= 0:
        return principal
    
    # Convert annual rate from percentage to decimal
    rate = annual_rate / 100
    
    # Compound interest formula: A = P(1 + r/n)^(nt)
    # where: A = final amount, P = principal, r = annual rate, n = compounding frequency, t = time in years
    amount = principal * ((1 + rate / compounding_frequency) ** (compounding_frequency * time_in_years))
    
    return amount


def calculate_current_value(fixed_deposits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calculate current value for active fixed deposits (excludes redeemed deposits).
    
    Args:
        fixed_deposits: List of fixed deposit holdings
    
    Returns:
        Enriched holdings with current_value and estimated_returns fields (only non-redeemed deposits)
    """
    enriched_deposits = []
    
    for deposit in fixed_deposits:
        # Skip redeemed deposits - they should not appear in the table
        if deposit.get('redeemed', False):
            continue
            
        deposit_copy = deposit.copy()
        
        # Parse deposit date: prefer reinvested date, but fall back to original investment date
        deposit_date_str = deposit.get('reinvested_date') or deposit.get('original_investment_date', '')
        deposit_date = None

        if deposit_date_str:
            try:
                deposit_date = datetime.strptime(deposit_date_str, "%B %d, %Y")
            except (ValueError, TypeError):
                # Fallback to year/month/day fields if main date parsing fails
                year = deposit.get('deposit_year')
                month = deposit.get('deposit_month')
                day = deposit.get('deposit_day')

                if year and month and day:
                    try:
                        deposit_date = datetime(int(year), int(month), int(day))
                    except (ValueError, TypeError) as e:
                        logger.warning("Error creating deposit date from year/month/day: %s", e)
        
        #Calculate maturity date from deposit period
        if deposit_date and deposit.get('deposit_year', 0) > 0:
            try:
                # Calculate maturity date by adding the deposit period
                total_days = int(deposit['deposit_year'] * 365)
                total_days += int(deposit.get('deposit_month', 0) * 30)
                total_days += int(deposit.get('deposit_day', 0))
                
                maturity_date = deposit_date + timedelta(days=total_days)
                maturity_date_str = maturity_date.strftime("%B %d, %Y")
                deposit_copy['maturity_date'] = maturity_date_str
                
                logger.debug(
                    "Calculated maturity date for %s: %s (Period: %dy %dm %dd)",
                    deposit['bank_name'],
                    maturity_date_str,
                    int(deposit['deposit_year']),
                    int(deposit.get('deposit_month', 0)),
                    int(deposit.get('deposit_day', 0))
                )
            except Exception as e:
                logger.error("Error calculating maturity date for %s: %s", deposit['bank_name'], e)
                raise DataError(
                    f"Cannot calculate maturity date for deposit at {deposit['bank_name']}: "
                    f"deposit period provided but calculation failed"
                )
        else:
            # Neither maturity date nor valid deposit period provided
            raise DataError(
                f"Missing maturity date for deposit at {deposit['bank_name']}: "
                f"provide either maturity date (Till column) or deposit period (Year/Month/Day)"
            )
        
        # Get principal and interest rate
        principal = deposit.get('reinvested_amount', 0) or deposit.get('original_amount', 0)
        annual_rate = deposit.get('interest_rate', 0)
        
        if deposit_date and principal > 0 and annual_rate > 0:
            # Calculate till today since non-redeemed deposits are auto-reinvested
            days_elapsed = (datetime.now() - deposit_date).days
            years_elapsed = days_elapsed / 365.0
            
            # Calculate current value with quarterly compound interest
            current_value = calculate_compound_interest(
                principal, 
                annual_rate, 
                years_elapsed, 
                compounding_frequency=4
            )
            
            deposit_copy['current_value'] = current_value
            deposit_copy['estimated_returns'] = current_value - principal
            
            enriched_deposits.append(deposit_copy)
        else:
            # Raise error if calculation not possible
            bank_name = deposit.get('bank_name', 'unknown')
            if not deposit_date:
                raise DataError(f"Missing deposit date for fixed deposit at {bank_name}")
            elif principal <= 0:
                raise DataError(f"Invalid principal amount ({principal}) for fixed deposit at {bank_name}")
            elif annual_rate <= 0:
                raise DataError(f"Invalid interest rate ({annual_rate}) for fixed deposit at {bank_name}")

    # Sort by maturity date in ascending order
    enriched_deposits.sort(
        key=lambda d: datetime.strptime(d['maturity_date'], "%B %d, %Y") if d.get('maturity_date') else datetime.max
    )

    return enriched_deposits
