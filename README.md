## Plaid Backend

## Description
Plaid Backend is an application built with django rest framework to supply APIs for using plaid to connect with customers of your e-commerce website and easily person queries on a dashboard to be build off the API, it contains transaction histories and is also connected to Stripe as a payment gateway. 

##  Setting up
- Install requirements
  pip install -r requirements.txt
 
- Make migrations
  python manage.py makemigrations
  
- Migrate
  python manage.py migrate
  
- Create an admin user
  python manage.py createsuperuser
   
- Runserver
  python manage.py runserver

## Contributing
- Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

- Please make sure to update tests as appropriate.

- Last updated: 2020.09.07.

