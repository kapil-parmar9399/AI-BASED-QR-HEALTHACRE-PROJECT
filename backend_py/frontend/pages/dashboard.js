import { useEffect, useState } from 'react';
import axios from 'axios';
import Link from 'next/link';

export default function Dashboard() {
    const [user, setUser] = useState(null);

    useEffect(() => {
        axios.get('/api/config/info').then(res => {
            setUser(res.data);
        }).catch(() => {});
    }, []);

    return ( <
        div className = "container" >
        <
        h1 > Dashboard < /h1> { user ? < pre > { JSON.stringify(user, null, 2) } < /pre> : <p>Loading...</p > } <
        p > < Link href = "/records" > < a > View Records < /a></Link > < /p> <
        p > < Link href = "/qr" > < a > Scan QR < /a></Link > < /p> <
        /div>
    );
}