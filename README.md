# Account System

## with Session Token based Authentication and End-to-End Encrypted Traffic

***

### Setting up the Server

#### Tested and written in Python 3.11. Older versions will not work. Support for arm64 subject to availability of pre-built wheels for the required packages.

Create a venv and run `pip install -r requirements.txt` inside it before following the next steps.

On the first execution of the server program, it asks the user for a folder where the server can store its operation files. In cases where the terminal can open a GUI, it opens a tkinter file selector dialogue and wherever it cannot do that, the user will be asked to input the file path in the command-line itself.

The user is asked for a password to lock the server to protect it from unauthorized access. This password will be used to encrypt the database credentials so that malicious actors with unauthorized access cannot hack into the database.

Then the database credentials, namely the MySQL/MariaDB server address, username, and password, are asked. The server then creates the necessary database and tables.

The server program then asks for the network address and port on which the server should listen to connections. This port must be open to the public on the server side to allow connections.

The server program will then close itself and will be ready for operation. When the server program is executed again, it asks for the password you entered. If a wrong password is entered, the server program closes at once.

When the correct password is entered, the server starts to listen for connections. At this state, users can connect to the server and perform their operations (sign up, login, authenticate and logout). 

***

### Problem Definition

To create a User Account Management System which can be used in various applications for safe and secure User Accounts.

This project consists of a Server program which can be executed on any computer with a network connection, and an example command-line Client, which users can use to connect to a server, create an account in the server and log into it.

The Server program is a WebSocket server which accepts packets from the client and performs the operations mentioned by the client (such as creating account, logging in, authenticating, etc.). This Server program is the base of the account management system.

The Client program is a command-line application for demonstrating the working of the server. When executed, the program displays an interactive command-line menu from where you can create an account, log in to an existing account or log out of the current session if logged in.

The messages exchanged between the Client and the Server are encrypted, meaning no one in the middle can intercept the packet and view user details.

The account credentials are safely stored in the server computer’s MySQL/MariaDB database in an encrypted format, which provides an additional level of security from the server’s owner/malicious actors.

This project aims to provide other developers with a secure way of handling accounts in their applications, helping them focus on the main functionality of their application.

This system can be implemented in various applications, such as chat platforms, social media platforms, and any other websites that require account creation. 

### Problem Analysis

#### Encrypted Traffic:

In cryptography, a key is a piece of information, usually a string of numbers or letters, that when processed through a cryptographic algorithm, can encode or decode cryptographic data. The key is used to transform data from plaintext (the original data) to ciphertext (the encrypted data). There are different methods for utilizing keys and encryption:

- Symmetric cryptography: The same key is used for both encryption and decryption.

- Asymmetric cryptography: Separate keys are used for encrypting and decrypting. These keys are known as the public and private keys.

Encrypting data is essential so that only the sender and intended recipient (in this case, the server) can read it. The type of encryption used in the client-server connection system of this project is based on asymmetric cryptography. The public key is used to encrypt the data, and the private key is used to decrypt it. The public key is shared with the recipient, but the private key is kept secret by the sender. The asymmetric encryption algorithm this project uses is RSA (Rivest-Shamir-Adleman). 

When a message is sent by the server, it is encrypted using the recipient's public key. The message can only be decrypted using the recipient's private key. Similarly, messages sent to the server by the client are encrypted using

the server’s public key. This means that even if an attacker intercepts the message, they will not be able to read it without the private key. In this application, the server’s public key will change with every restart for additional security. This diagram may give you more clarity: 

![image](https://github.com/user-attachments/assets/92820fbd-ae36-47f6-adcf-992a662fbeab)


This project does not utilize SSL/TLS or other methods of encrypting the connection as it requires special ports (number 80 and 443) to be open, and additional setup such as obtaining a certificate. Most consumer-oriented Internet Service Providers (ISPs) block the users from opening these ports, to prevent misuse. The process of obtaining a certificate is also tedious. This prevents the developers with not enough resources to buy a server from a hosting service/get their own enterprise network solution, from hosting this server. Therefore, the connection is encrypted with a different method to ensure security.

#### WebSocket Server:

WebSocket is a computer communications protocol that provides simultaneous two-way communication channels over a single Transmission Control Protocol (TCP) connection. Unlike HTTP, which is unidirectional, WebSocket is bidirectional and full duplex. This means the connection

between the client and the server is kept alive until it is terminated by either party. WebSocket URIs start with ws://

It facilitates real-time data transfer from and to the server. This is made possible by providing a standardized way for the server to send content to the client without being first requested by the client and allowing messages to be passed back and forth while keeping the connection open.

This is implemented in python by the websockets library built on top of python’s standard asynchronous input/output framework, asyncio. 

#### Asynchronous Operations

Asynchronous operations are tasks that can run concurrently without blocking or waiting for each other. They are useful for improving the performance and responsiveness of IO-bound applications, such as network and web servers, database connections, etc. Asynchronous operations can be executed using the async/await syntax, which allows writing code that looks like synchronous code, but is asynchronous.

asyncio is a built-in library in Python that provides support for asynchronous programming. It offers a framework and tools for creating and managing event loops, coroutines, tasks, futures, streams, transports, protocols, queues, and synchronization primitives. It also provides compatibility with other libraries and frameworks that use callbacks or generators.

websockets library is built on top of asyncio for its very function of asynchronous programming. WebSocket servers need to be able to handle multiple connections at once which is not possible synchronously. One connection would block the others, waiting for its own job to be complete. Asynchronous processing eliminates this block and allows for simultaneous connections and better performance. 

#### Hashing and Salting

Hashing is a process used in password security that involves converting a password into an unrecognizable series of characters. This is done using an irreversible hash function, which is a specialized algorithm. Instead of storing the password as plain text, a mathematical algorithm converts the password into a unique code. This unique code, or hash, is what gets stored in the database.

Salting is a technique used in password security to enhance the protection of passwords stored in a database. It involves adding a unique, random string of characters, known as a salt, to each password before it is hashed. This process changes the hash of the password, making it more secure.

Before the password is hashed, a salt value is added to it. This salted password is then hashed and stored in the database. Salting ensures that even if two users have the same password, their hashes will be different due to the unique salts. This halts attacks using precomputed tables of hashes, known as rainbow tables.

Moreover, salting makes it extra difficult for an attacker who gains access to password hashes to find out the original password. Even if an attacker manages to decrypt a salted password, the original password remains hidden. 

#### Authentication Token

An authentication token is a computer-generated code that securely transmits information about user identities between applications and websites. It allows users to access services without having to enter their login credentials each time. The user logs in once, and a unique token is generated and shared with connected applications or websites to verify their identity.

An authentication token is formed of three key components: the header (defines the token type and the signing algorithm), the payload (provides information about the user and other metadata), and the signature (verifies the authenticity of a message).

To generate the tokens, we use the open standard JSON Web Tokens (JWT). The token’s payload has 3 parts: sub, iat, and exp.

- sub: The ‘sub’ claim in a JWT stands for ‘subject’. It identifies the subject of the JWT, which is typically the user or the entity that the token represents. It’s a way to identify who the token is about.

- iat: The ‘iat’ claim stands for ‘Issued At’. It identifies the time at which the JWT was issued. The value must be a NumericDate, which is defined as the number of seconds (not milliseconds) since Epoch (1970-01-01T00:00:00Z UTC).

- exp: The ‘exp’ claim stands for ‘Expiration Time’. It identifies the expiration time on or after which the JWT must not be accepted for processing. Like ‘iat’, the value must be a NumericDate.

