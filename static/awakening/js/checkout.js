document.addEventListener('DOMContentLoaded', () => {
    const paymentForm = document.querySelector('#payment-form');
    if (!paymentForm) {
        return;
    }

    const stripePublicKey = paymentForm.dataset.stripeKey;
    const variantId = paymentForm.dataset.variantId;

    if (!stripePublicKey || !variantId) {
        console.error('Stripe public key or variant ID not found.');
        const cardElementDiv = document.querySelector('#card-element');
        if (cardElementDiv) {
            cardElementDiv.textContent = 'Error: Payment configuration is missing. Cannot load payment form.';
            cardElementDiv.classList.add('text-red-500');
        }
        return;
    }

    const stripe = Stripe(stripePublicKey);
    let elements;

    initialize();

    paymentForm.addEventListener('submit', handleFormSubmit);

    // Fetches a payment intent and captures the client secret
    async function initialize() {
        const response = await fetch('/create-payment-intent/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ variant_id: variantId }),
        });
        const { client_secret: clientSecret } = await response.json();

        elements = stripe.elements({ clientSecret });

        const cardElement = elements.create('card', {
            style: {
                base: {
                    color: '#fff',
                    fontFamily: '"VT323", monospace',
                    fontSize: '16px',
                    '::placeholder': { color: '#a0aec0' }
                },
                invalid: {
                    color: '#ef4444',
                    iconColor: '#ef4444'
                }
            }
        });
        cardElement.mount('#card-element');
        cardElement.on('change', ({ error }) => {
            const displayError = document.getElementById('card-errors');
            if (error) {
                displayError.textContent = error.message;
            } else {
                displayError.textContent = '';
            }
        });
    }

    async function handleFormSubmit(event) {
        event.preventDefault();
        setLoading(true);

        const email = document.querySelector('#email').value;
        const name = document.querySelector('#name').value;
        const address = document.querySelector('#address').value;
        const city = document.querySelector('#city').value;
        const postcode = document.querySelector('#postcode').value;

        const { error, paymentIntent } = await stripe.confirmPayment({
            elements,
            confirmParams: {
                // Return URL is not strictly needed for this SPA-like flow,
                // but good practice to have a fallback
                return_url: window.location.href, 
                payment_method_data: {
                    billing_details: {
                        name: name,
                        email: email,
                        address: {
                            line1: address,
                            city: city,
                            postal_code: postcode,
                            country: 'GB', // Assuming GB for now
                        }
                    }
                }
            },
            redirect: 'if_required' // Prevents redirect unless absolutely necessary
        });

        if (error) {
            handleError(error);
            return;
        }

        if (paymentIntent.status === 'succeeded') {
            // Payment succeeded, now create the order on the backend
            const orderData = {
                payment_intent_id: paymentIntent.id,
                email: email,
                name: name,
                address: address,
                city: city,
                postcode: postcode,
                variant_id: variantId,
            };

            const response = await fetch('/awakening/create-order/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify(orderData)
            });
            
            const serverResponse = await response.json();
            handleServerResponse(serverResponse);

        } else {
            document.getElementById('card-errors').textContent = "Payment not successful. Status: " + paymentIntent.status;
            setLoading(false);
        }
    }
    
    function handleServerResponse(response) {
        if (response.error) {
            document.getElementById('card-errors').textContent = response.error;
        } else if (response.success) {
            // Redirect to a success page or show a success message
            window.location.href = response.redirect_url;
        }
        setLoading(false);
    }

    function handleError(error) {
        let message = 'An unexpected error occurred.';
        if (error.type === 'card_error' || error.type === 'validation_error') {
            message = error.message;
        }
        document.getElementById('card-errors').textContent = message;
        setLoading(false);
    }

    function setLoading(isLoading) {
        const submitButton = document.getElementById('submit-button');
        if (isLoading) {
            submitButton.disabled = true;
            submitButton.textContent = 'PROCESSING...';
        } else {
            submitButton.disabled = false;
            submitButton.textContent = 'Submit Payment';
        }
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});