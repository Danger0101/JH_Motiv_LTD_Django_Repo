# core/shipping_policy_data.py

SHIPPING_POLICY_DATA = {
    'policy': {
        'title': 'Shipping & Delivery Policy',
        'effective_date': '31st October 2025',
        'contact': 'support@jhmotiv.shop',
        'sections': [
            {
                'heading': 'Overview: Print-on-Demand Model',
                'content': '<p>All products from JHMotiv.Shop are custom-made upon order through our partner, Printful. This means every item is created specifically for you after your purchase. Our delivery timeline is divided into two phases: <strong>Production Time</strong> and <strong>Shipping Time.</strong></p>',
            },
            {
                'heading': '1. Production Time (Processing)',
                'content': """
                    <p>This is the time it takes to create and prepare your item before it is shipped. Production time is separate from shipping time.</p>
                    <ul>
                        <li><strong>Standard Production:</strong> Typically <strong>2–7 business days</strong>.</li>
                        <li><strong>Peak Seasons:</strong> During holidays or major sales, production may take slightly longer.</li>
                    </ul>
                """,
            },
            {
                'heading': '2. Shipping Estimates & Costs',
                'content': """
                    <p>Shipping costs are calculated at checkout based on the delivery location and the weight/dimensions of your order. Below are estimated transit times after the item has been produced and shipped:</p>
                    
                    <h3>UK & Ireland</h3>
                    <ul>
                        <li><strong>Standard Shipping Time:</strong> 3–5 business days</li>
                        <li><strong>Cost Estimate:</strong> From £3.99</li>
                    </ul>
                    
                    <h3>Europe (EU & Non-EU)</h3>
                    <p>We use various carriers to ensure the best service across Europe.</p>
                    <ul>
                        <li><strong>Standard Shipping Time:</strong> 5–10 business days</li>
                        <li><strong>Cost Estimate:</strong> From £5.99</li>
                    </ul>
                    
                    <h3>USA & Canada</h3>
                    <ul>
                        <li><strong>Standard Shipping Time:</strong> 5–12 business days</li>
                        <li><strong>Cost Estimate:</strong> From £6.99</li>
                    </ul>

                    <h3>Rest of World</h3>
                    <ul>
                        <li><strong>Standard Shipping Time:</strong> 7–21 business days</li>
                        <li><strong>Cost Estimate:</strong> Varies significantly by location (calculated at checkout)</li>
                    </ul>
                """,
            },
            {
                'heading': '3. Tracking and Multiple Shipments',
                'content': """
                    <ul>
                        <li><strong>Tracking:</strong> You will receive a tracking number via email as soon as your order has shipped.</li>
                        <li><strong>Multiple Shipments:</strong> Orders containing multiple items (e.g., a mug and a t-shirt) may be produced and shipped separately from different facilities. If this occurs, you will receive separate tracking numbers, and items may arrive on different days.</li>
                    </ul>
                """,
            },
            {
                'heading': '4. Customs, Duties, and Taxes (Important for EU/International)',
                'content': """
                    <p>We are a UK-based company. Please be aware of the following:</p>
                    <ul>
                        <li><strong>EU Customers:</strong> The final checkout price <strong>includes VAT</strong> for EU orders, meaning you should not face additional charges upon delivery.</li>
                        <li><strong>International Customers (Outside UK/EU):</strong> Shipments may be subject to import duties and taxes which are levied once the package reaches your country. JHMotiv.Shop is <strong>not responsible</strong> for any customs duties, fees, or taxes applied by the destination country. These charges are the responsibility of the recipient.</li>
                        <li><strong>Customs Delays:</strong> Customs processing times can occasionally cause delays beyond our original delivery estimates.</li>
                    </ul>
                """,
            },
        ],
    }
}