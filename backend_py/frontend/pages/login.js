import { useState } from 'react';
import axios from 'axios';
import { useRouter } from 'next/router';

export default function Login() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const router = useRouter();

    const handleSubmit = async(e) => {
        e.preventDefault();
        try {
            await axios.post('/login', { username, password });
            router.push('/dashboard');
        } catch (err) {
            setError('Login failed');
        }
    };

    return ( <
        div className = "container" >
        <
        h1 > Login < /h1> {
            error && < p style = {
                    { color: 'red' } } > { error } < /p>} <
                form onSubmit = { handleSubmit } >
                <
                div >
                <
                label > Username: < /label> <
                input value = { username }
            onChange = {
                (e) => setUsername(e.target.value) }
            /> <
            /div> <
            div >
                <
                label > Password: < /label> <
                input type = "password"
            value = { password }
            onChange = {
                (e) => setPassword(e.target.value) }
            /> <
            /div> <
            button type = "submit" > Login < /button> <
                /form> <
                /div>
        );
    }