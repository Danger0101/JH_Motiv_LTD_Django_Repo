# core/refund_policy_data.py

REFUND_POLICY_DATA = {
    'retail': {
        'title': 'Refund and Replacement Policy: Retail',
        'effective_date': '1st April 2025',
        'sections': [
            {
                'heading': 'Overview (Made-to-Order Products)',
                'content': """
                    <p>At JHMotiv.Shop, all products (including apparel and custom DTF press orders) are custom-made on demand through our print partner, Printful. As such, returns are <strong>not available for buyer’s remorse</strong>, including:</p>
                    <ul>
                        <li>Ordering the wrong size or colour</li>
                        <li>Change of mind</li>
                        <li>Shipping delays outside our control</li>
                    </ul>
                    <p>This exemption is in accordance with your rights under the UK Consumer Contracts Regulations, which do not require us to accept returns for personalized or made-to-order goods.</p>
                """,
            },
            {
                'heading': 'When We Accept Returns or Refunds',
                'content': """
                    <p>We will offer a refund or replacement if:</p>
                    <ul>
                        <li>The item arrives <strong>damaged, defective, or misprinted</strong>.</li>
                        <li>The wrong item was delivered.</li>
                    </ul>
                    <p><strong>Custom DTF Press Orders:</strong> These items are non-refundable unless there is a clear manufacturing defect or if the law dictates otherwise.</p>
                """,
            },
            {
                'heading': 'How to Request a Replacement or Refund',
                'content': """
                    <p>To request a replacement or refund:</p>
                    <ol>
                        <li>Contact <strong>support@jhmotiv.shop</strong> within <strong>30 days</strong> of receiving your item.</li>
                        <li>Include your order number and clear photos showing the issue (damage, defect, or wrong item).</li>
                    </ol>
                """,
            },
            {
                'heading': 'Non-Returnable Items',
                'content': """
                    <ul>
                        <li>Custom-made items (including apparel and custom DTF press orders), except where defective.</li>
                        <li>Gift cards or digital downloads.</li>
                        <li>Discounted or sale items.</li>
                        <li>Any return request submitted after 30 days from delivery.</li>
                    </ul>
                """,
            },
            {
                'heading': 'Refund Process and Replacements',
                'content': """
                    <p>Once your claim is verified and approved, you’ll be notified by email. Refunds are issued to your original payment method within <strong>5–10 working days</strong>. We are happy to replace items if they are defective, damaged, or misprinted. We do <strong>not</strong> offer size exchanges due to our made-to-order model.</p>
                """,
            },
            {
                'heading': 'Gifts and Returns',
                'content': '<p>If the item was marked as a gift and is defective or incorrect, we can issue store credit or a replacement. If a return is required, we will provide the correct return address. Do <strong>not</strong> return any item until instructed — returns sent without approval may not be processed.</p>',
            },
            {
                'heading': 'Summary of Your Rights (UK)',
                'content': '<p>You have a legal right to receive goods that match their description and are of satisfactory quality. Since our products are custom-made, the 14-day cancellation right under Regulation 28(1)(b) of the Consumer Contracts Regulations 2013 does <strong>not</strong> apply to our products.</p>',
            },
        ],
    },
    'coaching': {
        'title': 'Refund Policy: Coaching Programs',
        'effective_date': '2nd October 2025',
        'sections': [
            {
                'heading': 'Overview',
                'content': '<p>We offer two distinct policies depending on the structure of your coaching program. Please refer to your program agreement to confirm the policy that applies to you.</p>',
            },
            {
                'heading': 'Option A: First Session Satisfaction Guarantee (Individual Sessions/Short Packages)',
                'content': """
                    <p>If, after completing your <strong>first scheduled coaching session</strong>, you feel the program is not the right fit, you may request a full refund of your program fee, subject to the following conditions:</p>
                    <ul>
                        <li><strong>100% Refund Window:</strong> You must notify us in writing (via email) of your cancellation intent within <strong>7 Days</strong> of the completion time of your first session.</li>
                        <li><strong>Commitment:</strong> If a second coaching session is attended, or if the 7 Day window closes without a refund request, you are considered fully committed. <strong>No further refunds (full or partial) will be issued</strong> for any reason.</li>
                        <li><strong>Access Termination:</strong> Upon processing the refund, your access to all digital materials and remaining sessions will be immediately terminated.</li>
                    </ul>
                """,
            },
            {
                'heading': 'Option B: For Long-Term Programs',
                'content': """
                    <p>Our long-term programs require mutual effort. To qualify for a refund, you must demonstrate active participation and implementation of the initial materials.</p>
                    <ul>
                        <li><strong>Eligibility Window:</strong> You must request a refund in writing to <strong>support@jhmotiv.shop</strong> within <strong>23 calendar days</strong> of your purchase <em>OR</em> prior to attending the <strong>third coaching session</strong>, whichever comes first.</li>
                        <li><strong>Required Proof of Work:</strong> Your refund request must include proof that you have:
                            <ul>
                                <li>Attended <strong>all scheduled coaching sessions</strong> on time (no more than 10 minutes late).</li>
                                <li>Completed action items assigned during the first session.</li>
                            </ul>
                        </li>
                    </ul>
                    <p><strong>Ineligible Requests:</strong> Requests made after the eligibility window, or without the required proof of work, will <strong>not be eligible</strong> for a refund.</p>
                """,
            },
        ],
    },
}