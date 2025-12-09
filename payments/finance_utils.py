from decimal import Decimal

def calculate_coaching_split(order_total, offering, referrer=None, client=None):
    """
    Distributes the order total between Coach, Referrer, and Company.
    Logic: 
    1. Calculate Referral Fee first (Top-line expense).
    2. Calculate Coach Share from the REMAINDER (Net Revenue).
    3. Company keeps the rest.
    """
    total = Decimal(str(order_total))
    
    # 1. Calculate Finder's Fee
    referral_fee = Decimal('0.00')
    if referrer:
        # Anti-Self-Dealing Check: Block commission if the client is the referrer.
        is_self_referral = client and referrer.user == client
        
        if not is_self_referral:
            if offering.referral_commission_type == 'percent':
                referral_fee = total * (offering.referral_commission_value / Decimal('100'))
            else:
                referral_fee = offering.referral_commission_value
        else:
            print(f"Self-referral detected for user {client.id}. Commission blocked.")

    # Ensure we don't pay out more than the total
    if referral_fee > total:
        referral_fee = total

    # 2. Calculate Remainder (Net Revenue after marketing cost)
    net_revenue = total - referral_fee
    
    # 3. Calculate Coach Share
    coach_share = net_revenue * (offering.coach_revenue_share / Decimal('100'))
    
    # 4. Company Share
    company_share = net_revenue - coach_share
    
    # Ensure the sum of splits equals the total, adjusting company share if needed
    total_split = referral_fee + coach_share + company_share
    company_share += total - total_split
    
    return {
        'referrer': referral_fee.quantize(Decimal('0.01')),
        'coach': coach_share.quantize(Decimal('0.01')),
        'company': company_share.quantize(Decimal('0.01'))
    }