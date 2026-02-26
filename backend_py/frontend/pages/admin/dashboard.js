import { useEffect, useState } from 'react';
import axios from 'axios';

export default function AdminDashboard() {
    const [data, setData] = useState(null);

    useEffect(() => {
        axios.get('/api/health').then(res => {
            setData(res.data);
        });
    }, []);

    return ( <
        div className = "container" >
        <
        h1 > Admin Dashboard < /h1> { data ? < pre > { JSON.stringify(data, null, 2) } < /pre> : <p>Loading...</p > } <
        /div>
    );
}