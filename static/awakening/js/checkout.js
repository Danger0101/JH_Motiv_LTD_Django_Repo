document.addEventListener('DOMContentLoaded', () => {
    const paymentForm = document.querySelector('#payment-form');
    if (!paymentForm) {
        return;
    }

    const stripePublicKey = paymentForm.dataset.stripeKey;
    if (!stripePublicKey) {
        console.error('Stripe public key not found.');
        // Optionally display an error to the user in the UI
        const cardElementDiv = document.querySelector('#card-element');
        if(cardElementDiv) {
            cardElementDiv.textContent = 'Error: Payment provider key is missing. Cannot load payment form.';
            cardElementDiv.classList.add('text-red-500');
        }
        return;
    }

    const stripe = Stripe(stripePublicKey);

    const elements = stripe.elements();
    const cardElement = elements.create('card', {
        style: {
            base: {
                color: '#fff',
                fontFamily: '"VT323", monospace',
                fontSize: '16px',
                '::placeholder': {
                    color: '#a0aec0'
                }
            },
            invalid: {
                color: '#ef4444',
                iconColor: '#ef4444'
            }
        }
    });

    cardElement.mount('#card-element');

    cardElement.on('change', ({error}) => {
        const displayError = document.getElementById('card-errors');
        if (error) {
            displayError.textContent = error.message;
        } else {
            displayError.textContent = '';
        }
    });

    paymentForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        // Simple form validation example
        const email = document.querySelector('#email').value;
        if (!email) {
            alert('Please enter your email address.');
            return;
        }

        console.log("Form submitted. Creating payment method...");

        const { error, paymentMethod } = await stripe.createPaymentMethod({
            type: 'card',
            card: cardElement,
            billing_details: {
                email: email,
            },
        });

        if (error) {
            console.error(error);
            const displayError = document.getElementById('card-errors');
            displayError.textContent = error.message;
        } else {
            console.log('Payment method created:', paymentMethod);
            // Here you would send the paymentMethod.id to your backend
            // to confirm the payment and create an order.
            alert('Payment method created successfully! Check the console. Next step is backend processing.');
        }
    });
});